# Dividend Reinvestment (DRIP) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On each ex-dividend date, automatically reinvest dividends as fractional shares for both the agent's held positions and the VOO benchmark account, and include a DRIP summary in the daily run2 Telegram report.

**Architecture:** A new `agent/tools/dividends.py` module handles all dividend logic — fetching ex-div data from yfinance, computing fractional reinvestment, and persisting to a new `dividend_events` table (idempotent via UNIQUE constraint). It is called from `cmd_run2` in `main.py` after trades execute, and its results are forwarded to `notify_run2` for Telegram display.

**Tech Stack:** Python 3.12, SQLite (existing `database.py`), yfinance, existing `notify.py` and `benchmark.py` patterns.

---

## File Map

| File | Change |
|------|--------|
| `agent/portfolio/database.py` | Add `dividend_events` table to `_DDL` |
| `agent/tools/dividends.py` | Create — `process_dividends(db_path, _today)` + `_get_dividend_today(ticker, today)` |
| `agent/tools/notify.py` | Add `dividends` param to `notify_run2()` |
| `agent/main.py` | Call `process_dividends()` in `cmd_run2`, pass to `notify_run2` |
| `tests/test_dividends.py` | Create — 6 tests |
| `tests/test_notify.py` | Add 1 test for dividends block in `notify_run2` |
| `tests/test_main.py` | Add 1 test that `cmd_run2` calls `process_dividends` |

---

## Task 1: Add `dividend_events` table and `process_dividends()`

**Files:**
- Modify: `agent/portfolio/database.py`
- Create: `agent/tools/dividends.py`
- Create: `tests/test_dividends.py`

### Schema

The `dividend_events` table records each DRIP event. The `UNIQUE(date, ticker, account)` constraint makes the function idempotent — calling it twice on the same day never double-pays.

```sql
CREATE TABLE IF NOT EXISTS dividend_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    date          TEXT NOT NULL,
    ticker        TEXT NOT NULL,
    account       TEXT NOT NULL CHECK(account IN ('agent','benchmark')),
    shares_held   REAL NOT NULL,
    div_per_share REAL NOT NULL,
    shares_added  REAL NOT NULL,
    UNIQUE(date, ticker, account)
);
```

- [ ] **Step 1: Write the failing tests**

Create `tests/test_dividends.py`:

```python
"""Tests for agent/tools/dividends.py — DRIP dividend reinvestment."""

from datetime import date

import pytest

from agent.portfolio.database import get_connection, init_db
from agent.portfolio.engine import execute_buy
from agent.tools.dividends import process_dividends


def _db(tmp_path):
    db = str(tmp_path / "portfolio.db")
    init_db(db)
    return db


def test_process_dividends_no_positions_returns_empty(tmp_path):
    """Returns empty list when agent holds no positions."""
    db = _db(tmp_path)
    result = process_dividends(db, _today=date(2026, 4, 17))
    assert result == []


def test_process_dividends_no_dividend_today_returns_empty(tmp_path, monkeypatch):
    """Returns empty list when held ticker has no dividend today."""
    db = _db(tmp_path)
    execute_buy("NVDA", 10, 100.0, "test", db_path=db)

    monkeypatch.setattr("agent.tools.dividends._get_dividend_today", lambda ticker, today: None)
    monkeypatch.setattr("agent.tools.dividends._get_current_price", lambda ticker: 100.0)

    result = process_dividends(db, _today=date(2026, 4, 17))
    assert result == []


def test_process_dividends_agent_reinvests_fractional_shares(tmp_path, monkeypatch):
    """Agent DRIP: dividend cash buys fractional shares, no cash change."""
    db = _db(tmp_path)
    execute_buy("NVDA", 10, 100.0, "test", db_path=db)

    monkeypatch.setattr("agent.tools.dividends._get_dividend_today", lambda ticker, today: 0.10)
    monkeypatch.setattr("agent.tools.dividends._get_current_price", lambda ticker: 100.0)

    result = process_dividends(db, _today=date(2026, 4, 17))

    # 10 shares * $0.10 dividend = $1.00 cash; $1.00 / $100.0 = 0.01 new shares
    assert len(result) == 1
    ev = result[0]
    assert ev["ticker"] == "NVDA"
    assert ev["account"] == "agent"
    assert abs(ev["shares_added"] - 0.01) < 1e-6
    assert abs(ev["div_per_share"] - 0.10) < 1e-6

    # Position shares increased
    conn = get_connection(db)
    row = conn.execute("SELECT shares FROM positions WHERE ticker='NVDA'").fetchone()
    conn.close()
    assert abs(row["shares"] - 10.01) < 1e-6

    # Cash unchanged (DRIP — no cash payout)
    from agent.portfolio.engine import get_portfolio_status
    portfolio = get_portfolio_status(db)
    assert abs(portfolio["cash"] - (10000.0 - 10 * 100.0)) < 0.01


def test_process_dividends_is_idempotent(tmp_path, monkeypatch):
    """Calling process_dividends twice on same day only processes once."""
    db = _db(tmp_path)
    execute_buy("NVDA", 10, 100.0, "test", db_path=db)

    monkeypatch.setattr("agent.tools.dividends._get_dividend_today", lambda ticker, today: 0.10)
    monkeypatch.setattr("agent.tools.dividends._get_current_price", lambda ticker: 100.0)

    today = date(2026, 4, 17)
    process_dividends(db, _today=today)
    result2 = process_dividends(db, _today=today)

    # Second call returns empty — already processed
    assert result2 == []

    # Shares only added once
    conn = get_connection(db)
    row = conn.execute("SELECT shares FROM positions WHERE ticker='NVDA'").fetchone()
    conn.close()
    assert abs(row["shares"] - 10.01) < 1e-6


def test_process_dividends_benchmark_voo_reinvests(tmp_path, monkeypatch):
    """Benchmark DRIP: VOO dividend adds fractional shares to benchmark_account."""
    db = _db(tmp_path)

    # Seed benchmark_account as if update_benchmark ran previously
    conn = get_connection(db)
    conn.execute(
        "INSERT INTO benchmark_account (id, voo_shares, total_deposited) VALUES (1, 22.5, 10000.0)"
    )
    conn.commit()
    conn.close()

    def _fake_div(ticker, today):
        return 1.50 if ticker == "VOO" else None

    monkeypatch.setattr("agent.tools.dividends._get_dividend_today", _fake_div)
    monkeypatch.setattr("agent.tools.dividends._get_current_price", lambda ticker: 450.0)

    result = process_dividends(db, _today=date(2026, 4, 17))

    # 22.5 shares * $1.50 = $33.75 dividend; $33.75 / $450.0 = 0.075 new shares
    bench_events = [e for e in result if e["account"] == "benchmark"]
    assert len(bench_events) == 1
    assert abs(bench_events[0]["shares_added"] - 0.075) < 1e-6

    conn = get_connection(db)
    row = conn.execute("SELECT voo_shares FROM benchmark_account WHERE id=1").fetchone()
    conn.close()
    assert abs(row["voo_shares"] - 22.575) < 1e-6


def test_process_dividends_skips_ticker_when_price_unavailable(tmp_path, monkeypatch):
    """Skips a position gracefully when get_price returns None."""
    db = _db(tmp_path)
    execute_buy("NVDA", 10, 100.0, "test", db_path=db)

    monkeypatch.setattr("agent.tools.dividends._get_dividend_today", lambda ticker, today: 0.10)
    monkeypatch.setattr("agent.tools.dividends._get_current_price", lambda ticker: None)

    result = process_dividends(db, _today=date(2026, 4, 17))
    assert result == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_dividends.py -v
```

Expected: 6 FAIL — `ModuleNotFoundError: No module named 'agent.tools.dividends'`

- [ ] **Step 3: Add `dividend_events` to `agent/portfolio/database.py`**

In `_DDL`, after the `benchmark_snapshots` table definition, add:

```python
_DDL = """
CREATE TABLE IF NOT EXISTS account (
    id      INTEGER PRIMARY KEY,
    cash    REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS positions (
    ticker    TEXT PRIMARY KEY,
    shares    REAL NOT NULL,
    avg_cost  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS trades (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT DEFAULT CURRENT_TIMESTAMP,
    action      TEXT NOT NULL CHECK(action IN ('BUY','SELL')),
    ticker      TEXT NOT NULL,
    shares      REAL NOT NULL,
    price       REAL NOT NULL,
    total       REAL NOT NULL,
    reasoning   TEXT
);

CREATE TABLE IF NOT EXISTS daily_snapshots (
    date         TEXT PRIMARY KEY,
    total_value  REAL NOT NULL,
    cash         REAL NOT NULL,
    pnl_pct      REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS benchmark_account (
    id              INTEGER PRIMARY KEY,
    voo_shares      REAL NOT NULL,
    total_deposited REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS benchmark_snapshots (
    date            TEXT PRIMARY KEY,
    voo_shares      REAL NOT NULL,
    voo_price       REAL NOT NULL,
    total_value     REAL NOT NULL,
    total_deposited REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS dividend_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    date          TEXT NOT NULL,
    ticker        TEXT NOT NULL,
    account       TEXT NOT NULL CHECK(account IN ('agent','benchmark')),
    shares_held   REAL NOT NULL,
    div_per_share REAL NOT NULL,
    shares_added  REAL NOT NULL,
    UNIQUE(date, ticker, account)
);
"""
```

- [ ] **Step 4: Create `agent/tools/dividends.py`**

```python
"""
dividends.py — DRIP dividend reinvestment for agent positions and VOO benchmark.
On each ex-dividend date, dividends are reinvested as fractional shares.
Never raises — returns [] on any error so run2 is never blocked.
"""

from __future__ import annotations

from datetime import date

from agent.portfolio.database import DB_PATH, get_connection, init_db


def process_dividends(db_path: str = DB_PATH, _today: date | None = None) -> list[dict]:
    """
    Check each held position and the VOO benchmark for ex-dividend events today.
    Reinvest as fractional shares. Idempotent via UNIQUE(date, ticker, account).
    Returns list of event dicts (one per reinvestment), or [] if nothing happened.
    """
    try:
        today = _today or date.today()
        today_str = today.isoformat()

        init_db(db_path)
        events: list[dict] = []

        conn = get_connection(db_path)
        try:
            # --- Agent positions ---
            pos_rows = conn.execute(
                "SELECT ticker, shares FROM positions"
            ).fetchall()

            for pos in pos_rows:
                ticker = pos["ticker"]
                shares_held = pos["shares"]

                already = conn.execute(
                    "SELECT 1 FROM dividend_events WHERE date=? AND ticker=? AND account='agent'",
                    (today_str, ticker),
                ).fetchone()
                if already:
                    continue

                div_per_share = _get_dividend_today(ticker, today)
                if not div_per_share:
                    continue

                current_price = _get_current_price(ticker)
                if not current_price:
                    continue

                dividend_cash = div_per_share * shares_held
                shares_added = dividend_cash / current_price

                conn.execute(
                    "UPDATE positions SET shares = shares + ? WHERE ticker = ?",
                    (shares_added, ticker),
                )
                conn.execute(
                    "INSERT INTO dividend_events (date, ticker, account, shares_held, div_per_share, shares_added) "
                    "VALUES (?, ?, 'agent', ?, ?, ?)",
                    (today_str, ticker, shares_held, div_per_share, shares_added),
                )
                conn.commit()

                events.append({
                    "ticker": ticker,
                    "account": "agent",
                    "shares_held": shares_held,
                    "div_per_share": div_per_share,
                    "shares_added": shares_added,
                    "total_dividend": dividend_cash,
                })

            # --- VOO benchmark ---
            bench_row = conn.execute(
                "SELECT voo_shares FROM benchmark_account WHERE id=1"
            ).fetchone()

            if bench_row:
                voo_shares = bench_row["voo_shares"]

                already = conn.execute(
                    "SELECT 1 FROM dividend_events WHERE date=? AND ticker='VOO' AND account='benchmark'",
                    (today_str,),
                ).fetchone()

                if not already:
                    div_per_share = _get_dividend_today("VOO", today)
                    if div_per_share:
                        current_price = _get_current_price("VOO")
                        if current_price:
                            dividend_cash = div_per_share * voo_shares
                            shares_added = dividend_cash / current_price

                            conn.execute(
                                "UPDATE benchmark_account SET voo_shares = voo_shares + ? WHERE id=1",
                                (shares_added,),
                            )
                            conn.execute(
                                "INSERT INTO dividend_events (date, ticker, account, shares_held, div_per_share, shares_added) "
                                "VALUES (?, 'VOO', 'benchmark', ?, ?, ?)",
                                (today_str, voo_shares, div_per_share, shares_added),
                            )
                            conn.commit()

                            events.append({
                                "ticker": "VOO",
                                "account": "benchmark",
                                "shares_held": voo_shares,
                                "div_per_share": div_per_share,
                                "shares_added": shares_added,
                                "total_dividend": dividend_cash,
                            })

        finally:
            conn.close()

        return events

    except Exception as exc:
        print(f"[dividends] process_dividends error: {exc}")
        return []


def _get_dividend_today(ticker: str, today: date) -> float | None:
    """Return dividend per share if today is ex-dividend date for ticker, else None."""
    try:
        import yfinance as yf
        divs = yf.Ticker(ticker).dividends
        if divs is None or divs.empty:
            return None
        for dt, amount in divs.items():
            if hasattr(dt, "date"):
                dt = dt.date()
            if dt == today:
                return float(amount)
        return None
    except Exception:
        return None


def _get_current_price(ticker: str) -> float | None:
    """Fetch current price for ticker. Returns None on failure."""
    try:
        from agent.tools.stock_data import get_price
        return get_price(ticker)
    except Exception:
        return None
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/test_dividends.py -v
```

Expected: 6 PASS

- [ ] **Step 6: Run full suite**

```bash
python -m pytest -x -q
```

Expected: all existing tests pass + 6 new.

- [ ] **Step 7: Commit**

```bash
git add agent/portfolio/database.py agent/tools/dividends.py tests/test_dividends.py
git commit -m "feat(FEAT-005): add dividend_events table and process_dividends"
```

---

## Task 2: Wire `process_dividends()` into `cmd_run2`

**Files:**
- Modify: `agent/main.py`
- Test: `tests/test_main.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_main.py`:

```python
# FEAT-005
def test_cmd_run2_calls_process_dividends(tmp_path, monkeypatch, capsys):
    """cmd_run2 calls process_dividends and does not crash when no dividends."""
    from datetime import datetime as _dt
    from zoneinfo import ZoneInfo
    db_file = str(tmp_path / "portfolio.db")
    plan_file = str(tmp_path / "run1_plan.json")
    out_file = str(tmp_path / "output" / "dashboard.html")

    init_db(db_file)

    plan = {
        "decisions": {
            "trades": [],
            "skip_new_buys": False,
            "briefing": "ok",
        }
    }
    with open(plan_file, "w") as f:
        json.dump(plan, f)

    _market_open_et = _dt(2026, 4, 17, 10, 0, tzinfo=ZoneInfo("America/New_York"))
    dividend_calls = []

    def _fake_dividends(db_path, _today=None):
        dividend_calls.append(db_path)
        return []

    monkeypatch.setattr("agent.main.process_dividends", _fake_dividends)
    monkeypatch.setattr("agent.tools.notify.send_telegram", lambda msg: True)
    monkeypatch.setattr("agent.tools.benchmark._get_voo_price", lambda: 450.0)

    with patch("agent.main.datetime") as mock_dt:
        mock_dt.now.return_value = _market_open_et
        mock_dt.side_effect = lambda *a, **kw: _dt(*a, **kw)
        cmd_run2(db_path=db_file, plan_path=plan_file, output_path=out_file)

    assert len(dividend_calls) == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_main.py::test_cmd_run2_calls_process_dividends -v
```

Expected: FAIL — `AttributeError: module 'agent.main' has no attribute 'process_dividends'`

- [ ] **Step 3: Add import to `agent/main.py`**

Find the existing imports block and add:

```python
from agent.tools.dividends import process_dividends  # FEAT-005
```

Add it after the `from agent.tools.benchmark import update_benchmark` line.

- [ ] **Step 4: Call `process_dividends` in `cmd_run2`**

In `cmd_run2`, find the line `benchmark = update_benchmark(db_path)` and add the dividends call immediately after it:

```python
        benchmark = update_benchmark(db_path)  # FEAT-002: must run before dashboard
        dividends = process_dividends(db_path)  # FEAT-005
```

Then update the `notify_run2` call at the bottom to pass `dividends`:

```python
        notify_run2(executed, rejected, portfolio, benchmark=benchmark, dividends=dividends)  # FEAT-002, FEAT-005
```

- [ ] **Step 5: Run test to verify it passes**

```bash
python -m pytest tests/test_main.py::test_cmd_run2_calls_process_dividends -v
```

Expected: PASS

- [ ] **Step 6: Run full suite**

```bash
python -m pytest -x -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add agent/main.py tests/test_main.py
git commit -m "feat(FEAT-005): wire process_dividends into cmd_run2"
```

---

## Task 3: Add dividends block to `notify_run2()`

**Files:**
- Modify: `agent/tools/notify.py`
- Test: `tests/test_notify.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_notify.py`:

```python
# FEAT-005
def test_notify_run2_includes_dividends_block(monkeypatch):
    """notify_run2 shows DRIP block when dividends are present."""
    sent = []
    monkeypatch.setattr("agent.tools.notify.send_telegram", lambda msg: sent.append(msg) or True)

    from agent.tools.notify import notify_run2
    notify_run2(
        executed=[],
        rejected=[],
        portfolio={"cash": 5000.0, "total_value": 10200.0, "pnl_pct": 2.0},
        dividends=[
            {
                "ticker": "NVDA",
                "account": "agent",
                "shares_held": 10.0,
                "div_per_share": 0.10,
                "shares_added": 0.01,
                "total_dividend": 1.0,
            },
            {
                "ticker": "VOO",
                "account": "benchmark",
                "shares_held": 22.5,
                "div_per_share": 1.50,
                "shares_added": 0.075,
                "total_dividend": 33.75,
            },
        ],
    )

    assert len(sent) == 1
    msg = sent[0]
    assert "📈 Dividends" in msg
    assert "NVDA" in msg
    assert "0.0100" in msg or "+0.01" in msg
    assert "VOO" in msg
    assert "benchmark" in msg


def test_notify_run2_no_dividends_block_when_empty(monkeypatch):
    """notify_run2 omits DRIP block when dividends list is empty."""
    sent = []
    monkeypatch.setattr("agent.tools.notify.send_telegram", lambda msg: sent.append(msg) or True)

    from agent.tools.notify import notify_run2
    notify_run2(
        executed=[],
        rejected=[],
        portfolio={"cash": 5000.0, "total_value": 10200.0, "pnl_pct": 2.0},
        dividends=[],
    )

    assert "📈 Dividends" not in sent[0]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_notify.py::test_notify_run2_includes_dividends_block tests/test_notify.py::test_notify_run2_no_dividends_block_when_empty -v
```

Expected: 2 FAIL — `TypeError: notify_run2() got an unexpected keyword argument 'dividends'`

- [ ] **Step 3: Update `notify_run2()` signature and body**

In `agent/tools/notify.py`, find `def notify_run2(` and update the full function:

```python
def notify_run2(  # FEAT-002: added benchmark param; FEAT-005: added dividends param
    executed: list[str],
    rejected: list[str],
    portfolio: dict,
    benchmark: dict | None = None,
    dividends: list[dict] | None = None,
) -> None:
    """Send run2 execution results to Telegram."""
    lines = ["<b>Investment Agent — Trades Executed</b>", ""]

    if executed:
        lines.append("<b>Executed:</b>")
        for msg in executed:
            lines.append(f"  {msg}")
    else:
        lines.append("No trades executed.")

    if rejected:
        lines.append("")
        lines.append("<b>Rejected:</b>")
        for msg in rejected:
            lines.append(f"  {msg}")

    cash = portfolio.get("cash", 0.0)
    total = portfolio.get("total_value", 0.0)
    pnl = portfolio.get("pnl_pct", 0.0)
    lines.append("")
    lines.append(f"Cash: ${cash:,.2f} | Total: ${total:,.2f} | P&amp;L: {pnl:+.2f}%")

    # FEAT-002: benchmark comparison block
    if benchmark:
        voo_total = benchmark.get("total_value", 0.0)
        deposited = benchmark.get("total_deposited", 10_000.0)
        agent_pnl = (total - deposited) / deposited * 100 if deposited else 0.0
        voo_pnl = (voo_total - deposited) / deposited * 100 if deposited else 0.0
        lines.append("")
        lines.append("<b>📊 Benchmark (VOO buy &amp; hold):</b>")
        lines.append(f"  Agent: ${total:,.0f} ({agent_pnl:+.1f}%)")
        lines.append(f"  VOO:   ${voo_total:,.0f} ({voo_pnl:+.1f}%)")
        lines.append(f"  Deposited: ${deposited:,.0f} each")
        if benchmark.get("deposit_made"):
            lines.append("  +$100 deposited to both today")

    # FEAT-005: dividend reinvestment block
    if dividends:
        lines.append("")
        lines.append("<b>📈 Dividends Reinvested (DRIP):</b>")
        for ev in dividends:
            ticker = _esc(ev.get("ticker", "?"))
            account = ev.get("account", "agent")
            shares_added = ev.get("shares_added", 0.0)
            total_div = ev.get("total_dividend", 0.0)
            label = f"{ticker}" if account == "agent" else f"{ticker} (benchmark)"
            lines.append(f"  {label}: +{shares_added:.4f} shares (${total_div:.2f})")

    send_telegram("\n".join(lines))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_notify.py::test_notify_run2_includes_dividends_block tests/test_notify.py::test_notify_run2_no_dividends_block_when_empty -v
```

Expected: 2 PASS

- [ ] **Step 5: Run full suite**

```bash
python -m pytest -x -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add agent/tools/notify.py tests/test_notify.py
git commit -m "feat(FEAT-005): add dividends DRIP block to notify_run2"
```

---

## Self-Review

**Spec coverage:**
- ✅ Agent held stocks get dividends on ex-div date (Task 1 — agent positions loop)
- ✅ VOO benchmark gets dividends (Task 1 — benchmark section)
- ✅ Fractional shares reinvested (Task 1 — `shares_added = dividend_cash / price`)
- ✅ Idempotent — won't double-pay (Task 1 — UNIQUE constraint + early-return check)
- ✅ Included in daily run2 Telegram report (Task 3 — DRIP block in notify_run2)
- ✅ Wire into cmd_run2 (Task 2)

**Placeholder scan:** None found — all steps have complete code.

**Type consistency:**
- `process_dividends` returns `list[dict]` — Task 2 assigns to `dividends`, Task 3 consumes it ✅
- `notify_run2(..., dividends: list[dict] | None = None)` — Task 3 signature matches Task 2 call ✅
- `_get_dividend_today` and `_get_current_price` used consistently across Task 1 code and tests ✅
