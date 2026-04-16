# Project Context — AI Investment Agent

**Last updated:** 2026-04-15
**Tests:** 69 passing, 0 failing

---

## What This Is

Fully autonomous paper trading agent. Runs on cron. Uses Claude Code CLI (`claude --print`) as the AI — no Anthropic API key needed. Targets 15% return ($11,500) from $10,000 in 30 trading days.

---

## Build Status

| Task | File(s) | Status |
|------|---------|--------|
| ✅ 1 | `requirements.txt`, `agent/`, `tests/` structure | Done |
| ✅ 2 | `agent/portfolio/database.py` | Done |
| ✅ 3 | `agent/portfolio/engine.py` | Done |
| ✅ 4 | `agent/tools/stock_data.py`, `agent/tools/market_index.py` | Done |
| ✅ 5 | `agent/tools/technical.py`, `agent/tools/screener.py` | Done |
| ✅ 6 | `agent/tools/risk_rules.py` | Done |
| ✅ 7 | `agent/claude_agent.py` | Done |
| ✅ 8 | `agent/tools/dashboard.py` | Done |
| ✅ 9 | `agent/main.py` (CLI + cron) | Done |

---

## Architecture (quick ref)

```
Run 1 (6:00 AM PT):  market_index → screener → claude_agent → save run1_plan.json
Run 2 (6:30 AM PT):  read plan → risk_rules → engine.execute_buy/sell → dashboard
Intraday (30 min):   engine positions → risk_rules.check_stop_loss/profit_target → auto-sell
```

Claude is called only in Run 1. `claude --print <prompt>` returns `<decisions>` JSON. No API key.

---

## Key Design Decisions

- **No `anthropic` SDK** — uses `subprocess.run(["claude", "--print", prompt])`
- **4 risk rules:** 25% max position, -7% stop-loss, +12% profit target, max 3 positions
- **Run 1 saves `data/run1_plan.json`** — Run 2 reads it (decoupled)
- **Intraday monitor needs no Claude call** — pure math stop-loss/profit checks
- **HTML dashboard** — self-contained file, Chart.js via CDN

---

## File Structure

```
investmentAgent/
├── agent/
│   ├── main.py                  ← TODO (Task 9)
│   ├── claude_agent.py          ← TODO (Task 7)
│   ├── tools/
│   │   ├── stock_data.py        ✅ get_price, get_history, get_company_info
│   │   ├── market_index.py      ✅ get_market_direction → risk_on/neutral/risk_off
│   │   ├── technical.py         ✅ calculate_indicators, get_momentum_score (0-100)
│   │   ├── screener.py          ✅ screen_stocks(market_direction) → sorted list
│   │   ├── risk_rules.py        ✅ validate_buy/sell, check_stop_loss/profit_target
│   │   └── dashboard.py         ← TODO (Task 8)
│   └── portfolio/
│       ├── database.py          ✅ init_db, get_connection, 4-table schema
│       └── engine.py            ✅ execute_buy, execute_sell, get_portfolio_status
├── data/portfolio.db            (auto-created, gitignored)
├── data/run1_plan.json          (Run 1 → Run 2 handoff, gitignored)
├── output/dashboard.html        (generated, gitignored)
├── docs/
│   ├── 20260414-PRD-investment-agent.md
│   └── 20260414-ARD-investment-agent.md
└── tests/                       41 tests passing
```

---

## Claude Prompt Format (Task 7)

Claude receives one structured prompt with all pre-fetched data. Returns:
```json
{
  "trades": [{"action":"BUY","ticker":"NVDA","shares":5,"reasoning":"..."}],
  "skip_new_buys": false,
  "briefing": "plain-English market summary"
}
```
Wrapped in `<decisions>...</decisions>` tags. Parsed with regex + json.loads.

---

## Watchlist (18 stocks)
NVDA, AMD, TSLA, META, AMZN, GOOGL, MSFT, AAPL, COIN, PLTR, CRWD, SNOW, NET, QQQ, SOXL, SOXS, MSTR, IONQ

---

## Run Commands (once fully built)
```bash
python -m agent.main run1      # 6:00 AM PT — scan + Claude decision
python -m agent.main run2      # 6:30 AM PT — execute trades
python -m agent.main monitor   # every 30 min — stop-loss/profit check
python -m agent.main history   # view trade log
python -m agent.main dashboard # regenerate HTML
```
