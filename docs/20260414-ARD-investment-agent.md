# Architecture Requirements Document
# AI Investment Agent — US Stock Momentum Trader

**Version:** 1.2
**Date:** 2026-04-14
**Owner:** Gary
**Status:** Approved

---

## 1. System Overview

The Investment Agent is a local Python application that runs on Gary's Mac or Linux machine via scheduled cron jobs. It has no server, no web UI backend, and no cloud infrastructure. All state is stored in a local SQLite database. External calls go to one service: Yahoo Finance via yfinance (market data). AI reasoning is provided by the **Claude Code CLI** (`claude --print`) — no Anthropic API key required.

```
┌─────────────────────────────────────────────────────────────┐
│                    Gary's Mac / Linux                       │
│                                                             │
│  ┌──────────────┐    ┌────────────────┐   ┌─────────────┐  │
│  │  Scheduler   │    │  Claude Agent  │   │  Portfolio  │  │
│  │  (cron)      │───▶│  (Orchestrator)│──▶│   Engine    │  │
│  │ 6:00AM Run1  │    │                │   │  (SQLite)   │  │
│  │ 6:30AM Run2  │    └───────┬────────┘   └─────────────┘  │
│  └──────────────┘            │                             │
│                      ┌───────▼────────┐                    │
│                      │  Tool Layer    │                    │
│                      │ ┌────────────┐ │                    │
│                      │ │stock_data  │ │                    │
│                      │ │technical   │ │                    │
│                      │ │market_index│ │                    │
│                      │ │screener    │ │                    │
│                      │ │risk_rules  │ │                    │
│                      │ │dashboard   │ │                    │
│                      └───────┬────────┘                    │
│                              │                             │
│  ┌───────────────────────────▼──────────────────────────┐  │
│  │  Output                                              │  │
│  │  dashboard.html  |  portfolio.db  |  run_log.txt     │  │
│  └──────────────────────────────────────────────────────┘  │
└──────────────────────────────┬──────────────────────────────┘
                               │ External calls
               ┌───────────────┴───────────────┐
               ▼                               ▼
       ┌──────────────┐               ┌──────────────┐
       │ Claude Code  │               │   yfinance   │
       │ CLI (local)  │               │ (Yahoo Data) │
       │ claude--print│               │              │
       └──────────────┘               └──────────────┘
```

**Key architectural decision: Claude Code CLI as the AI engine**

The agent calls Claude Code via `subprocess.run(["claude", "--print", prompt])`. It does **not** use the `anthropic` Python SDK and requires **no API key**. Because `claude --print` is a single-turn call, all market data is gathered by Python tools first, then passed to Claude in one structured prompt. Claude returns a structured JSON response inside `<decisions>` tags.

This means:
- No `ANTHROPIC_API_KEY` in `.env`
- No `anthropic` package in `requirements.txt`
- All tool functions (`screen_top_stocks`, `analyze_stock`, etc.) are called by Python, not by Claude natively
- Claude receives pre-assembled context and returns a decision — it does not drive a tool-use loop

---

## 2. Daily Run Schedule

| Run | Time (PT) | Time (ET) | Purpose |
|---|---|---|---|
| Run 1 | 6:00 AM | 9:00 AM | Pre-market scan, generate trade plan, save to JSON |
| Run 2 | 6:30 AM | 9:30 AM | Execute plan at market open, update dashboard |
| Intraday | Every 30 min | 6:30 AM – 1:00 PM PT | Monitor stop-loss and profit targets (no Claude call needed) |
| Weekends | Skip | — | No-op |
| Holidays | Skip | — | No-op |

**Scheduler:** `crontab` (Mac and Linux) or macOS `launchd` (Mac only via `.plist` files).

**Intraday note:** Stop-loss and profit target checks are pure math — no Claude call is made during monitoring. Only Run 1 and Run 2 call Claude Code CLI.

---

## 3. Component Architecture

### 3.1 Entry Point — `agent/main.py`

**Responsibility:** CLI entry point. Routes to Run 1, Run 2, intraday monitor, or history command.

**Commands:**
```bash
python -m agent.main run1       # Morning scan + plan (calls Claude Code CLI)
python -m agent.main run2       # Execute plan
python -m agent.main monitor    # Intraday position check (no Claude call)
python -m agent.main history    # Print all trades with reasoning
python -m agent.main dashboard  # Regenerate HTML dashboard
```

---

### 3.2 Claude Agent — `agent/claude_agent.py`

**Responsibility:** AI brain. Gathers all context via tool functions, builds a structured prompt, calls Claude Code CLI, parses the response.

**Pattern (gather-then-ask, single turn):**
```
1. Call market_index.get_market_direction()   → NASDAQ/S&P500 trend
2. Call screener.screen_top_stocks()           → ranked candidates with scores
3. Call engine.get_portfolio_status()          → cash, positions, P&L
4. Build one structured prompt (all data above + risk rules + 15% goal status)
5. subprocess.run(["claude", "--print", prompt]) → Claude reasons and returns JSON
6. Parse <decisions> JSON block from stdout
7. Return list of trade decisions to caller
```

**Claude Code CLI call:**
```python
import subprocess

result = subprocess.run(
    ["claude", "--print", prompt],
    capture_output=True,
    text=True,
    timeout=120,
)
response_text = result.stdout
```

**No `anthropic` import. No API key. No SDK.**

**Model used:** Whatever Claude model is active in Gary's Claude Code installation (currently claude-sonnet-4-6).

**Prompt structure sent to Claude:**

```
You are an autonomous momentum trading agent managing a $10,000 paper portfolio.
Goal: achieve 15% return ($11,500) within 30 trading days.

RISK RULES (enforced in code — your decisions will be validated against these):
1. Max 25% of portfolio in any single position
2. Stop-loss: -7% from avg cost (auto-sell trigger)
3. Profit target: +12% (auto-sell trigger)
4. Max 3 open positions

MARKET DIRECTION (today):
{market_direction_block}

PORTFOLIO STATUS:
{portfolio_block}

WATCHLIST MOMENTUM SCORES (pre-calculated):
{screened_stocks_block}

OUTPUT — respond with JSON inside <decisions> tags:
<decisions>
{
  "trades": [
    {"action": "BUY", "ticker": "NVDA", "shares": 5, "reasoning": "..."},
    {"action": "SELL", "ticker": "TSLA", "shares": 3, "reasoning": "..."}
  ],
  "skip_new_buys": false,
  "briefing": "2-3 sentence plain-English market summary and strategy for today."
}
</decisions>
```

**Parse strategy:** Regex extracts `<decisions>...</decisions>`, then JSON parsed. On failure: log raw output, skip all trades, record error.

---

### 3.3 Tool Layer — `agent/tools/`

All tools are called by Python **before** the Claude prompt is built. Claude receives their output as formatted text, not as live callable functions.

#### `stock_data.py`
**Responsibility:** Raw data fetching from yfinance.

| Function | Input | Output |
|---|---|---|
| `get_price(ticker)` | ticker | float — latest price |
| `get_history(ticker, period)` | ticker, period | OHLCV DataFrame |
| `get_company_info(ticker)` | ticker | dict — sector, market cap, 52w range |

#### `market_index.py`
**Responsibility:** Fetch NASDAQ (^IXIC) and S&P500 (^GSPC) to determine overall market direction.

| Function | Output |
|---|---|
| `get_market_direction()` | dict: `{nasdaq_change_pct, sp500_change_pct, direction}` |

**Direction logic:**
- Both indexes up >0.5%: `"risk_on"` — favorable for momentum buys
- Either index down >1%: `"risk_off"` — skip new buys, passed to Claude as context
- Otherwise: `"neutral"`

#### `technical.py`
**Responsibility:** Momentum indicators for individual stocks.

| Function | Output |
|---|---|
| `calculate_indicators(df)` | DataFrame with RSI, MACD, MACD_signal, SMA_20, Volume_SMA_20 |
| `get_momentum_score(ticker, df)` | dict: score (0-100), signals list, RSI value |

**Momentum Score (0-100):**

| Signal | Bullish | Bearish |
|---|---|---|
| Baseline | +50 | — |
| RSI 55-70 | +15 | — |
| RSI > 70 (overbought) | — | -10 |
| RSI < 40 | — | -15 |
| MACD above signal | +15 | — |
| MACD below signal | — | -10 |
| MACD histogram rising | +5 | — |
| Price above SMA-20 | +10 | — |
| Price below SMA-20 | — | -10 |
| Volume > 1.5x avg | +5 | — |

#### `screener.py`
**Responsibility:** Scan watchlist, score each stock, return ranked list for Claude's prompt.

**Watchlist (18 stocks):** NVDA, AMD, TSLA, META, AMZN, GOOGL, MSFT, AAPL, COIN, PLTR, CRWD, SNOW, NET, QQQ, SOXL, SOXS + 2 TBD.

**Output format passed to Claude:**
```
Ticker | Score | RSI  | MACD  | vs SMA20 | Signals
NVDA   | 85    | 62.1 | above | +3.2%    | RSI bullish, MACD cross, high volume
TSLA   | 71    | 58.4 | above | +1.8%    | RSI bullish, MACD above signal
...
```

#### `risk_rules.py`
**Responsibility:** Enforce the 4 hardcoded risk rules in code. Called before every trade execution in Run 2 and intraday monitor.

```python
def validate_buy(ticker, shares, price, portfolio) -> tuple[bool, str]:
    """Returns (allowed, reason). All 4 rules checked."""

def validate_sell(ticker, shares, portfolio) -> tuple[bool, str]:
    """Validates sell is permissible."""

def check_stop_loss(ticker, current_price, avg_cost) -> bool:
    """Returns True if stop-loss threshold (-7%) is breached."""

def check_profit_target(ticker, current_price, avg_cost) -> bool:
    """Returns True if profit target (+12%) is hit."""
```

**The 4 rules:**
1. Max 25% of total portfolio value per position
2. Stop-loss at -7% (auto-sell trigger)
3. Profit target at +12% (auto-sell trigger)
4. Max 3 open positions

#### `dashboard.py`
**Responsibility:** Generate a self-contained HTML dashboard from current DB state.

**Output:** `output/dashboard.html` — single file, no external dependencies except Chart.js via CDN, opens in any browser.

**Dashboard sections:**
1. Header: total value, cash, P&L%, progress bar toward 15% ($11,500)
2. Open positions table: ticker, shares, avg cost, current price, unrealized P&L%
3. Trade history table: date, action, ticker, shares, price, Claude's reasoning
4. 30-day P&L line chart (Chart.js via CDN)

---

### 3.4 Portfolio Engine — `agent/portfolio/`

#### `database.py`
**Responsibility:** All SQLite read/write. No business logic.

**Schema:**

```sql
-- Cash balance
CREATE TABLE account (
    id      INTEGER PRIMARY KEY,
    cash    REAL NOT NULL
);

-- Open positions
CREATE TABLE positions (
    ticker    TEXT PRIMARY KEY,
    shares    REAL NOT NULL,
    avg_cost  REAL NOT NULL
);

-- Full trade history with AI reasoning
CREATE TABLE trades (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT DEFAULT CURRENT_TIMESTAMP,
    action      TEXT NOT NULL,       -- 'BUY' or 'SELL'
    ticker      TEXT NOT NULL,
    shares      REAL NOT NULL,
    price       REAL NOT NULL,
    total       REAL NOT NULL,       -- shares * price
    reasoning   TEXT                 -- Claude's plain-English reasoning
);

-- Daily portfolio snapshots for 30-day chart
CREATE TABLE daily_snapshots (
    date         TEXT PRIMARY KEY,   -- YYYY-MM-DD
    total_value  REAL NOT NULL,
    cash         REAL NOT NULL,
    pnl_pct      REAL NOT NULL
);
```

#### `engine.py`
**Responsibility:** Business logic — buy, sell, position tracking, daily snapshots.

---

### 3.5 Output Files

| File | Updated when | Purpose |
|---|---|---|
| `output/dashboard.html` | After Run 2 + intraday monitor | Visual portfolio dashboard |
| `output/run_log.txt` | Every run | Plain-text log of each run |
| `data/portfolio.db` | Every trade | Persistent state |
| `data/run1_plan.json` | After Run 1 | Trade plan (Claude's decisions) passed to Run 2 |

---

## 4. Data Flow

### Run 1 (6:00 AM PT — Pre-market)

```
1. main.py            Triggers Run 1
2. market_index.py    get_market_direction() → NASDAQ/S&P500 trend
3. screener.py        screen_top_stocks() → scored + ranked candidates
4. engine.py          get_portfolio_status() → current positions + cash
5. claude_agent.py    Builds one structured prompt with all of the above
6. Claude Code CLI    subprocess("claude --print <prompt>") → returns <decisions> JSON
7. claude_agent.py    Parses JSON → list of trade decisions
8. main.py            Saves decisions to data/run1_plan.json
9. main.py            Prints morning briefing (Claude's "briefing" field) to terminal + run_log.txt
```

### Run 2 (6:30 AM PT — Market Open)

```
1. main.py            Triggers Run 2
2. main.py            Reads data/run1_plan.json
3. For each trade decision:
   a. risk_rules.py   validate_buy/sell() — blocks if any rule violated
   b. stock_data.py   get_price() → current price via yfinance
   c. engine.py       execute_buy/sell() → writes to SQLite with reasoning
4. dashboard.py       Regenerates output/dashboard.html
5. main.py            Prints execution summary to terminal + run_log.txt
```

### Intraday Monitor (Every 30 min, 6:30 AM – 1:00 PM PT)

```
1. engine.py          Load open positions from SQLite
2. stock_data.py      get_price() for each held ticker
3. risk_rules.py      check_stop_loss() and check_profit_target() for each position
4. If stop-loss triggered (-7%):
   a. engine.py       execute_sell() with reasoning = "stop-loss at -7% triggered"
   b. database.py     Save trade to SQLite
   c. dashboard.py    Regenerate dashboard
5. If profit target triggered (+12%):
   a. engine.py       execute_sell() with reasoning = "profit target +12% hit"
   b. database.py     Save trade to SQLite
   c. dashboard.py    Regenerate dashboard

NOTE: No Claude Code CLI call during intraday monitoring — pure math only.
```

---

## 5. Technology Stack

| Component | Technology | Version | Why |
|---|---|---|---|
| Language | Python | 3.11+ | Best AI/finance library ecosystem; Mac + Linux |
| AI Engine | Claude Code CLI | installed | No API key; uses Gary's subscription; `claude --print` |
| Market Data | yfinance | >=0.2.40 | Free, no API key required |
| Technical Analysis | ta | >=0.11.0 | RSI/MACD/SMA implementations |
| Database | SQLite (built-in) | — | No server; persists locally |
| Dashboard Charts | Chart.js | via CDN | No install needed; renders in any browser |
| Scheduler | crontab (Mac + Linux) | — | Cross-platform; launchd optional on Mac |
| Data processing | pandas | >=2.0.0 | DataFrame manipulation |
| Config | python-dotenv | >=1.0.0 | Environment config (no API keys needed) |
| Testing | pytest | >=8.0.0 | Standard Python testing |
| **NOT used** | anthropic SDK | — | **Replaced by Claude Code CLI subprocess** |

---

## 6. External Dependencies

| Service | Used for | Auth | Cost |
|---|---|---|---|
| Claude Code CLI | AI reasoning (Run 1 only) | None (existing subscription) | $0 extra |
| Yahoo Finance (yfinance) | Stock prices + history | None | Free |

**No Anthropic API key. No `.env` secrets for AI.**

---

## 7. File Structure

```
investmentAgent/
├── agent/
│   ├── __init__.py
│   ├── main.py                  # CLI entry point
│   ├── claude_agent.py          # Builds prompt, calls claude --print, parses response
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── stock_data.py        # yfinance wrapper
│   │   ├── market_index.py      # NASDAQ/S&P500 direction
│   │   ├── technical.py         # RSI, MACD, momentum score
│   │   ├── screener.py          # Watchlist scanner + ranker
│   │   ├── risk_rules.py        # 4 hardcoded risk rules
│   │   └── dashboard.py         # HTML dashboard generator
│   └── portfolio/
│       ├── __init__.py
│       ├── engine.py            # Business logic (buy/sell/snapshot)
│       └── database.py          # SQLite operations
├── tests/
│   ├── test_stock_data.py
│   ├── test_technical.py
│   ├── test_portfolio.py
│   ├── test_risk_rules.py
│   └── test_dashboard.py
├── data/
│   ├── portfolio.db             # SQLite (auto-created on init)
│   └── run1_plan.json           # Run 1 → Run 2 handoff (Claude's decisions)
├── output/
│   ├── dashboard.html           # Generated dashboard (open in browser)
│   └── run_log.txt              # Plain-text run log
├── docs/
│   ├── 20260414-PRD-investment-agent.md
│   └── 20260414-ARD-investment-agent.md
├── requirements.txt             # NO anthropic SDK
├── .env.example                 # No API keys needed
└── .gitignore
```

---

## 8. Security Considerations

- No API keys needed or stored
- No user data persisted beyond local SQLite
- No real brokerage connection in v1.0 — no real money at risk
- Claude Code CLI is a local subprocess — no data leaves the machine except to yfinance

---

## 9. Constraints and Limitations

| Constraint | Detail |
|---|---|
| 15-min delayed data | yfinance not suitable for day trading; fine for swing trades |
| Mac/Linux must be awake | Mac: enable "wake for network access" in Energy Saver |
| Internet required | yfinance needs internet; Claude Code CLI is local |
| Market hours only | yfinance returns stale data outside 9:30 AM – 4:00 PM ET |
| Equities only | No options, crypto, or non-US markets |
| Single-turn Claude calls | `claude --print` is one prompt → one response; no multi-turn tool loop |

---

## 10. Future Architecture (v2)

- **Real trading:** Add `tools/alpaca_broker.py`, swap paper engine for live Alpaca orders
- **News sentiment:** Fetch headlines before screening, include in Claude prompt
- **Backtesting:** Run scoring logic on historical data to validate strategy
- **Alerts:** Send daily summary via email or iMessage
- **Web UI:** FastAPI server + live-reload dashboard instead of static HTML
