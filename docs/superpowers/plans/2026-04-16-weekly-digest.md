# Weekly Performance Digest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every Sunday at 1pm PT, send a Telegram message summarising the week — trades made, P&L change, agent vs VOO comparison, and best/worst position.

**Architecture:** A new `agent/tools/weekly_report.py` queries the SQLite DB for the past 7 days and builds a structured report dict. A new `notify_weekly()` in `notify.py` formats and sends it. A new `cmd_weekly` in `main.py` ties them together. `run_agent.sh` gets a Sunday 1pm PT cron line.

**Tech Stack:** Python 3.12, SQLite (existing `database.py`), Telegram (existing `notify.py`), bash cron.

---

## File Map

| File | Change |
|------|--------|
| `agent/tools/weekly_report.py` | Create — `build_weekly_report(db_path, today)` returns report dict |
| `agent/tools/notify.py` | Add `notify_weekly(report)` |
| `agent/main.py` | Add `cmd_weekly()` + `"weekly"` route |
| `run_agent.sh` | Add Sunday 1pm PT cron comment |
| `tests/test_weekly_report.py` | Create — 5 tests for `build_weekly_report` |
| `tests/test_notify.py` | Add 2 tests for `notify_weekly` |
| `tests/test_main.py` | Add 1 test for `cmd_weekly` |

---

## Task 1: Create `agent/tools/weekly_report.py`

**Files:**
- Create: `agent/tools/weekly_report.py`
- Create: `tests/test_weekly_report.py`

- [ ] **Step 1: Create `tests/test_weekly_report.py` with failing tests**

```python
"""Tests for agent/tools/weekly_report.py — FEAT-004 weekly digest."""

from datetime import date

import pytest

from agent.portfolio.database import get_connection, init_db
from agent.tools.weekly_report import build_weekly_report


def _db(tmp_path):
    db = str(tmp_path / "portfolio.db")
    init_db(db)
    return db


# FEAT-004
def test_build_weekly_report_returns_expected_keys(tmp_path):
    """build_weekly_report returns dict with all required keys."""
    db = _db(tmp_path)
    result = build_weekly_report(db, today=date(2026, 4, 19))
    assert "week_start" in result
    assert "week_end" in result
    assert "trades" in result
    assert "agent_start_value" in result
    assert "agent_end_value" in result
    assert "agent_pnl_dollar" in result
    assert "agent_pnl_pct" in result
    assert "voo_start_value" in result
    assert "voo_end_value" in result
    assert "voo_pnl_dollar" in result
    assert "voo_pnl_pct" in result
    assert "best_ticker" in result
    assert "worst_ticker" in result


# FEAT-004
def test_build_weekly_report_week_bounds(tmp_path):
    """week_start is the Monday and week_end is the Sunday of the given date's week."""
    db = _db(tmp_path)
    result = build_weekly_report(db, today=date(2026, 4, 19))  # Sunday
    assert result["week_start"] == "2026-04-13"
    assert result["week_end"] == "2026-04-19"


# FEAT-004
def test_build_weekly_report_trades_from_this_week(tmp_path):
    """Only trades from Mon–Sun of this week appear in the report."""
    db = _db(tmp_path)
    conn = get_connection(db)
    # Insert one trade this week (Wednesday) and one last week
    conn.execute(
        "INSERT INTO trades (timestamp, action, ticker, shares, price, total, reasoning) "
        "VALUES ('2026-04-15 10:00:00', 'BUY', 'NVDA', 5, 100.0, 500.0, 'test')"
    )
    conn.execute(
        "INSERT INTO trades (timestamp, action, ticker, shares, price, total, reasoning) "
        "VALUES ('2026-04-06 10:00:00', 'BUY', 'AAPL', 3, 200.0, 600.0, 'old')"
    )
    conn.commit()
    conn.close()
    result = build_weekly_report(db, today=date(2026, 4, 19))
    assert len(result["trades"]) == 1
    assert result["trades"][0]["ticker"] == "NVDA"


# FEAT-004
def test_build_weekly_report_pnl_from_snapshots(tmp_path):
    """agent_pnl_dollar is end_value minus start_value from daily_snapshots."""
    db = _db(tmp_path)
    conn = get_connection(db)
    conn.execute(
        "INSERT INTO daily_snapshots (date, total_value, cash, pnl_pct) "
        "VALUES ('2026-04-13', 10000.0, 9000.0, 0.0)"
    )
    conn.execute(
        "INSERT INTO daily_snapshots (date, total_value, cash, pnl_pct) "
        "VALUES ('2026-04-18', 10500.0, 8500.0, 5.0)"
    )
    conn.commit()
    conn.close()
    result = build_weekly_report(db, today=date(2026, 4, 19))
    assert abs(result["agent_start_value"] - 10000.0) < 0.01
    assert abs(result["agent_end_value"] - 10500.0) < 0.01
    assert abs(result["agent_pnl_dollar"] - 500.0) < 0.01


# FEAT-004
def test_build_weekly_report_empty_db_returns_zeros(tmp_path):
    """With no snapshots or trades, returns zero values without raising."""
    db = _db(tmp_path)
    result = build_weekly_report(db, today=date(2026, 4, 19))
    assert result["agent_start_value"] == 0.0
    assert result["agent_end_value"] == 0.0
    assert result["trades"] == []
    assert result["best_ticker"] is None
    assert result["worst_ticker"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_weekly_report.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'agent.tools.weekly_report'`

- [ ] **Step 3: Create `agent/tools/weekly_report.py`**

```python
"""weekly_report.py — Build weekly performance summary from SQLite data.  # FEAT-004
Queries the past Mon–Sun week and returns a structured dict for notify_weekly().
Never raises — returns a zeroed dict on any error.
"""

from __future__ import annotations

from datetime import date, timedelta

from agent.portfolio.database import DB_PATH, get_connection, init_db


def build_weekly_report(db_path: str = DB_PATH, today: date | None = None) -> dict:  # FEAT-004
    """
    Build a weekly performance report for the Mon–Sun week containing `today`.
    Returns a dict with week bounds, trades, agent P&L, VOO P&L, best/worst ticker.
    Returns zeroed dict on any error.
    """
    try:
        today = today or date.today()
        # Monday of this week
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)  # Sunday

        init_db(db_path)
        conn = get_connection(db_path)
        try:
            # Trades this week
            trade_rows = conn.execute(
                "SELECT action, ticker, shares, price, total, timestamp "
                "FROM trades "
                "WHERE date(timestamp) BETWEEN ? AND ? "
                "ORDER BY timestamp",
                (week_start.isoformat(), week_end.isoformat()),
            ).fetchall()
            trades = [
                {
                    "action": r["action"],
                    "ticker": r["ticker"],
                    "shares": r["shares"],
                    "price": r["price"],
                    "total": r["total"],
                    "timestamp": r["timestamp"],
                }
                for r in trade_rows
            ]

            # Agent P&L: earliest and latest snapshot in window
            snap_start = conn.execute(
                "SELECT total_value FROM daily_snapshots "
                "WHERE date >= ? ORDER BY date ASC LIMIT 1",
                (week_start.isoformat(),),
            ).fetchone()
            snap_end = conn.execute(
                "SELECT total_value FROM daily_snapshots "
                "WHERE date <= ? ORDER BY date DESC LIMIT 1",
                (week_end.isoformat(),),
            ).fetchone()
            agent_start = snap_start["total_value"] if snap_start else 0.0
            agent_end = snap_end["total_value"] if snap_end else 0.0
            agent_pnl_dollar = agent_end - agent_start
            agent_pnl_pct = (agent_pnl_dollar / agent_start * 100) if agent_start else 0.0

            # VOO P&L: same approach from benchmark_snapshots
            voo_start_row = conn.execute(
                "SELECT total_value FROM benchmark_snapshots "
                "WHERE date >= ? ORDER BY date ASC LIMIT 1",
                (week_start.isoformat(),),
            ).fetchone()
            voo_end_row = conn.execute(
                "SELECT total_value FROM benchmark_snapshots "
                "WHERE date <= ? ORDER BY date DESC LIMIT 1",
                (week_end.isoformat(),),
            ).fetchone()
            voo_start = voo_start_row["total_value"] if voo_start_row else 0.0
            voo_end = voo_end_row["total_value"] if voo_end_row else 0.0
            voo_pnl_dollar = voo_end - voo_start
            voo_pnl_pct = (voo_pnl_dollar / voo_start * 100) if voo_start else 0.0

            # Best/worst ticker by P&L this week (from positions + trades)
            pos_rows = conn.execute(
                "SELECT ticker, shares, avg_cost FROM positions"
            ).fetchall()
            best_ticker = None
            worst_ticker = None
            if pos_rows:
                best_pnl = None
                worst_pnl = None
                for p in pos_rows:
                    from agent.tools.stock_data import get_price
                    price = get_price(p["ticker"])
                    if price is None:
                        continue
                    pnl = (price - p["avg_cost"]) / p["avg_cost"] * 100
                    if best_pnl is None or pnl > best_pnl:
                        best_pnl = pnl
                        best_ticker = p["ticker"]
                    if worst_pnl is None or pnl < worst_pnl:
                        worst_pnl = pnl
                        worst_ticker = p["ticker"]

            return {
                "week_start": week_start.isoformat(),
                "week_end": week_end.isoformat(),
                "trades": trades,
                "agent_start_value": agent_start,
                "agent_end_value": agent_end,
                "agent_pnl_dollar": agent_pnl_dollar,
                "agent_pnl_pct": agent_pnl_pct,
                "voo_start_value": voo_start,
                "voo_end_value": voo_end,
                "voo_pnl_dollar": voo_pnl_dollar,
                "voo_pnl_pct": voo_pnl_pct,
                "best_ticker": best_ticker,
                "worst_ticker": worst_ticker,
            }
        finally:
            conn.close()

    except Exception as exc:
        print(f"[weekly_report] build_weekly_report error: {exc}")
        return {
            "week_start": "", "week_end": "", "trades": [],
            "agent_start_value": 0.0, "agent_end_value": 0.0,
            "agent_pnl_dollar": 0.0, "agent_pnl_pct": 0.0,
            "voo_start_value": 0.0, "voo_end_value": 0.0,
            "voo_pnl_dollar": 0.0, "voo_pnl_pct": 0.0,
            "best_ticker": None, "worst_ticker": None,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_weekly_report.py -v
```

Expected: 5 PASS

- [ ] **Step 5: Run full suite**

```bash
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

Expected: all passing + 5 new.

- [ ] **Step 6: Commit**

```bash
git add agent/tools/weekly_report.py tests/test_weekly_report.py
git commit -m "feat(FEAT-004): add build_weekly_report"
```

---

## Task 2: Add `notify_weekly()` to `notify.py`

**Files:**
- Modify: `agent/tools/notify.py`
- Test: `tests/test_notify.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_notify.py`:

```python
# FEAT-004
def test_notify_weekly_sends_telegram(monkeypatch):
    """notify_weekly sends a Telegram message with key weekly metrics."""
    sent = []
    monkeypatch.setattr("agent.tools.notify.send_telegram", lambda msg: sent.append(msg) or True)

    from agent.tools.notify import notify_weekly
    notify_weekly({
        "week_start": "2026-04-13",
        "week_end": "2026-04-19",
        "trades": [
            {"action": "BUY", "ticker": "NVDA", "shares": 10, "price": 100.0,
             "total": 1000.0, "timestamp": "2026-04-15 10:00:00"},
        ],
        "agent_start_value": 10000.0,
        "agent_end_value": 10500.0,
        "agent_pnl_dollar": 500.0,
        "agent_pnl_pct": 5.0,
        "voo_start_value": 10000.0,
        "voo_end_value": 10200.0,
        "voo_pnl_dollar": 200.0,
        "voo_pnl_pct": 2.0,
        "best_ticker": "NVDA",
        "worst_ticker": None,
    })

    assert len(sent) == 1
    msg = sent[0]
    assert "Weekly" in msg
    assert "2026-04-13" in msg
    assert "2026-04-19" in msg
    assert "+$500" in msg or "+500" in msg
    assert "NVDA" in msg
    assert "VOO" in msg


# FEAT-004
def test_notify_weekly_handles_empty_report(monkeypatch):
    """notify_weekly sends without crashing when report has no trades or positions."""
    sent = []
    monkeypatch.setattr("agent.tools.notify.send_telegram", lambda msg: sent.append(msg) or True)

    from agent.tools.notify import notify_weekly
    notify_weekly({
        "week_start": "2026-04-13",
        "week_end": "2026-04-19",
        "trades": [],
        "agent_start_value": 0.0,
        "agent_end_value": 0.0,
        "agent_pnl_dollar": 0.0,
        "agent_pnl_pct": 0.0,
        "voo_start_value": 0.0,
        "voo_end_value": 0.0,
        "voo_pnl_dollar": 0.0,
        "voo_pnl_pct": 0.0,
        "best_ticker": None,
        "worst_ticker": None,
    })

    assert len(sent) == 1
    assert "Weekly" in sent[0]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_notify.py::test_notify_weekly_sends_telegram tests/test_notify.py::test_notify_weekly_handles_empty_report -v
```

Expected: FAIL — `ImportError: cannot import name 'notify_weekly'`

- [ ] **Step 3: Add `notify_weekly()` to `agent/tools/notify.py`**

```python
def notify_weekly(report: dict) -> None:  # FEAT-004
    """Send Sunday weekly digest to Telegram."""
    week_start = report.get("week_start", "")
    week_end = report.get("week_end", "")
    trades = report.get("trades", [])
    agent_end = report.get("agent_end_value", 0.0)
    agent_pnl_dollar = report.get("agent_pnl_dollar", 0.0)
    agent_pnl_pct = report.get("agent_pnl_pct", 0.0)
    voo_end = report.get("voo_end_value", 0.0)
    voo_pnl_dollar = report.get("voo_pnl_dollar", 0.0)
    voo_pnl_pct = report.get("voo_pnl_pct", 0.0)
    best_ticker = report.get("best_ticker")
    worst_ticker = report.get("worst_ticker")

    agent_sign = "+" if agent_pnl_dollar >= 0 else ""
    voo_sign = "+" if voo_pnl_dollar >= 0 else ""

    lines = [
        f"<b>📅 Weekly Digest — {week_start} to {week_end}</b>",
        "",
        "<b>Performance</b>",
        f"  Agent: ${agent_end:,.0f} ({agent_sign}${agent_pnl_dollar:,.0f}, {agent_sign}{agent_pnl_pct:.1f}%)",
        f"  VOO:   ${voo_end:,.0f} ({voo_sign}${voo_pnl_dollar:,.0f}, {voo_sign}{voo_pnl_pct:.1f}%)",
    ]

    if best_ticker or worst_ticker:
        lines.append("")
        lines.append("<b>Positions</b>")
        if best_ticker:
            lines.append(f"  Best:  {best_ticker}")
        if worst_ticker:
            lines.append(f"  Worst: {worst_ticker}")

    lines.append("")
    if trades:
        lines.append(f"<b>Trades this week ({len(trades)})</b>")
        for t in trades:
            date_str = t.get("timestamp", "")[:10]
            lines.append(
                f"  {date_str} {t['action']} {t['shares']} {t['ticker']} @ ${t['price']:,.2f}"
            )
    else:
        lines.append("No trades this week.")

    send_telegram("\n".join(lines))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_notify.py::test_notify_weekly_sends_telegram tests/test_notify.py::test_notify_weekly_handles_empty_report -v
```

Expected: 2 PASS

- [ ] **Step 5: Run full suite**

```bash
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

Expected: all passing.

- [ ] **Step 6: Commit**

```bash
git add agent/tools/notify.py tests/test_notify.py
git commit -m "feat(FEAT-004): add notify_weekly for Sunday digest"
```

---

## Task 3: Add `cmd_weekly` to `main.py` and wire cron

**Files:**
- Modify: `agent/main.py`
- Modify: `run_agent.sh`
- Test: `tests/test_main.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_main.py`:

```python
# FEAT-004
def test_cmd_weekly_sends_digest(tmp_path, monkeypatch, capsys):
    """cmd_weekly builds report and sends Telegram without raising."""
    db_file = str(tmp_path / "portfolio.db")
    init_db(db_file)

    monkeypatch.setattr("agent.tools.notify.send_telegram", lambda msg: True)
    monkeypatch.setattr("agent.tools.stock_data.get_price", lambda ticker: 100.0)

    from agent.main import cmd_weekly
    cmd_weekly(db_path=db_file)

    captured = capsys.readouterr()
    assert "Weekly digest sent" in captured.out
```

- [ ] **Step 2: Run test to verify it fails**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_main.py::test_cmd_weekly_sends_digest -v
```

Expected: FAIL — `ImportError: cannot import name 'cmd_weekly'`

- [ ] **Step 3: Add imports to `agent/main.py`**

Add to the imports block:

```python
from agent.tools.weekly_report import build_weekly_report  # FEAT-004
from agent.tools.notify import notify_error, notify_run1, notify_run2, notify_weekly  # FEAT-004: added notify_weekly
```

(Replace the existing `notify` import line with the updated one.)

- [ ] **Step 4: Add `cmd_weekly()` to `agent/main.py`**

Add after `cmd_dashboard`:

```python
def cmd_weekly(db_path: str = DB_PATH) -> None:  # FEAT-004
    """Build and send the weekly performance digest to Telegram."""
    try:
        init_db(db_path)
        report = build_weekly_report(db_path)
        notify_weekly(report)
        print("Weekly digest sent")
    except Exception as exc:
        notify_error("weekly", str(exc))
        print(f"Error: {exc}")
        sys.exit(1)
```

- [ ] **Step 5: Add `"weekly"` route to `main()` router**

In the `main()` function, add after the `"dashboard"` branch:

```python
    elif command == "weekly":
        cmd_weekly()
```

- [ ] **Step 6: Add cron line to `run_agent.sh`**

In `run_agent.sh`, find the cron setup comment block in `USAGE` (or the inline comment) and add:

```bash
# Weekly digest (Sunday 1pm PT = 20:00 UTC during PDT)
# 0 20 * * 0  cd /path/to/investmentAgent && python -m agent.main weekly >> logs/agent.log 2>&1
```

Add this as a comment block near the end of `run_agent.sh`, after the existing cron setup note at the top.

- [ ] **Step 7: Run test to verify it passes**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_main.py::test_cmd_weekly_sends_digest -v
```

Expected: PASS

- [ ] **Step 8: Run full suite**

```bash
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

Expected: all passing.

- [ ] **Step 9: Commit**

```bash
git add agent/main.py run_agent.sh tests/test_main.py
git commit -m "feat(FEAT-004): add cmd_weekly command and Sunday cron"
```
