# VOO Benchmark Comparison Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Track a parallel VOO buy-and-hold paper account alongside the AI agent, depositing $100 every Monday to both, and show the comparison in Telegram and the HTML dashboard.

**Architecture:** Same SQLite database gets two new tables (`benchmark_account`, `benchmark_snapshots`). A new `agent/tools/benchmark.py` handles all benchmark logic. `cmd_run2` in `main.py` does the Monday $100 agent cash deposit and calls `update_benchmark()`. `notify_run2` and `generate_dashboard` are extended with optional benchmark blocks. All new code tagged `# FEAT-002`.

**Tech Stack:** Python 3.12, SQLite (via existing `database.py`), yfinance (already installed), Chart.js CDN

---

## File Map

| File | Change |
|------|--------|
| `agent/portfolio/database.py` | Add 2 new tables to `_DDL` |
| `agent/tools/benchmark.py` | Create — `update_benchmark()` + `_get_voo_price()` |
| `agent/main.py` | Add Monday deposit + `update_benchmark()` call + `get_connection` import |
| `agent/tools/notify.py` | Extend `notify_run2()` with benchmark block |
| `agent/tools/dashboard.py` | Add benchmark section (summary cards + comparison chart), move CDN to `<head>` |
| `tests/test_database.py` | Add 1 test for new tables |
| `tests/test_benchmark.py` | Create — 5 tests |
| `tests/test_notify.py` | Add 2 tests for benchmark block in `notify_run2` |
| `tests/test_dashboard.py` | Add 2 tests for benchmark section |
| `tests/test_main.py` | Add 1 test for Monday deposit |

---

## Task 1: Add benchmark tables to `database.py`

**Files:**
- Modify: `agent/portfolio/database.py` (`_DDL` string)
- Test: `tests/test_database.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_database.py`:

```python
# FEAT-002
def test_benchmark_tables_exist_after_init_db(tmp_path):
    """init_db creates benchmark_account and benchmark_snapshots tables."""
    db = str(tmp_path / "portfolio.db")
    init_db(db)
    conn = get_connection(db)
    try:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    finally:
        conn.close()
    assert "benchmark_account" in tables
    assert "benchmark_snapshots" in tables
```

Make sure `get_connection` is imported at the top of `tests/test_database.py`. Check the existing imports — if it's not there, add: `from agent.portfolio.database import DB_PATH, get_connection, init_db`

- [ ] **Step 2: Run test to verify it fails**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_database.py::test_benchmark_tables_exist_after_init_db -v
```

Expected: FAIL — `assert "benchmark_account" in tables`

- [ ] **Step 3: Add tables to `_DDL` in `agent/portfolio/database.py`**

Append to the `_DDL` string, before the closing `"""`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_database.py::test_benchmark_tables_exist_after_init_db -v
```

Expected: PASS

- [ ] **Step 5: Run full suite to confirm no regressions**

```bash
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

Expected: 76 passed + 1 new = 77 passed.

- [ ] **Step 6: Commit**

```bash
git add agent/portfolio/database.py tests/test_database.py
git commit -m "feat(FEAT-002): add benchmark_account and benchmark_snapshots tables"
```

---

## Task 2: Create `agent/tools/benchmark.py`

**Files:**
- Create: `agent/tools/benchmark.py`
- Create: `tests/test_benchmark.py`

- [ ] **Step 1: Create `tests/test_benchmark.py` with failing tests**

```python
"""Tests for agent/tools/benchmark.py — FEAT-002 VOO benchmark."""

from datetime import date

import pytest

from agent.portfolio.database import get_connection, init_db
from agent.tools.benchmark import update_benchmark


def _db(tmp_path):
    db = str(tmp_path / "portfolio.db")
    init_db(db)
    return db


# FEAT-002
def test_update_benchmark_seeds_on_first_run(tmp_path, monkeypatch):
    """First call seeds $10,000 into VOO at current price, no deposit flag."""
    monkeypatch.setattr("agent.tools.benchmark._get_voo_price", lambda: 450.0)
    db = _db(tmp_path)
    result = update_benchmark(db, _today=date(2026, 4, 16))  # Thursday
    assert result["voo_price"] == 450.0
    assert abs(result["voo_shares"] - 10000.0 / 450.0) < 0.0001
    assert result["total_deposited"] == 10000.0
    assert result["deposit_made"] is False
    assert abs(result["total_value"] - 10000.0) < 0.01


# FEAT-002
def test_update_benchmark_monday_deposit(tmp_path, monkeypatch):
    """Monday call adds $100 fractional shares and sets deposit_made=True."""
    monkeypatch.setattr("agent.tools.benchmark._get_voo_price", lambda: 450.0)
    db = _db(tmp_path)
    update_benchmark(db, _today=date(2026, 4, 16))  # Thursday — seed
    result = update_benchmark(db, _today=date(2026, 4, 20))  # Monday
    assert result["deposit_made"] is True
    assert result["total_deposited"] == 10100.0
    expected_shares = 10000.0 / 450.0 + 100.0 / 450.0
    assert abs(result["voo_shares"] - expected_shares) < 0.0001


# FEAT-002
def test_update_benchmark_non_monday_no_deposit(tmp_path, monkeypatch):
    """Non-Monday call does not deposit."""
    monkeypatch.setattr("agent.tools.benchmark._get_voo_price", lambda: 450.0)
    db = _db(tmp_path)
    update_benchmark(db, _today=date(2026, 4, 16))  # Thursday — seed
    result = update_benchmark(db, _today=date(2026, 4, 17))  # Friday
    assert result["deposit_made"] is False
    assert result["total_deposited"] == 10000.0


# FEAT-002
def test_update_benchmark_idempotent_same_monday(tmp_path, monkeypatch):
    """Calling twice on the same Monday only deposits once."""
    monkeypatch.setattr("agent.tools.benchmark._get_voo_price", lambda: 450.0)
    db = _db(tmp_path)
    monday = date(2026, 4, 14)
    update_benchmark(db, _today=date(2026, 4, 10))  # Thursday — seed
    update_benchmark(db, _today=monday)              # First Monday call
    result2 = update_benchmark(db, _today=monday)   # Second Monday call — same day
    assert result2["total_deposited"] == 10100.0     # Only one $100 deposit
    assert result2["deposit_made"] is False          # Second call didn't deposit


# FEAT-002
def test_update_benchmark_returns_empty_on_price_failure(tmp_path, monkeypatch):
    """Returns {} without raising when VOO price cannot be fetched."""
    monkeypatch.setattr("agent.tools.benchmark._get_voo_price", lambda: None)
    db = _db(tmp_path)
    result = update_benchmark(db)
    assert result == {}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_benchmark.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'agent.tools.benchmark'`

- [ ] **Step 3: Create `agent/tools/benchmark.py`**

```python
"""benchmark.py — VOO buy-and-hold benchmark tracker.
Tracks a parallel $10,000 account that buys VOO immediately and adds $100 every Monday.
Never raises — returns {} on any error so run2 is never blocked.
"""

from __future__ import annotations

from datetime import date

from agent.portfolio.database import DB_PATH, get_connection, init_db

INITIAL_DEPOSIT = 10_000.0
WEEKLY_DEPOSIT = 100.0


def update_benchmark(db_path: str = DB_PATH, _today: date | None = None) -> dict:  # FEAT-002
    """
    Called every run2. Handles first-run seeding, Monday deposits, and daily snapshots.
    _today is injectable for testing; defaults to date.today().
    Returns status dict or {} on any error.
    """
    try:
        today = _today or date.today()
        today_str = today.isoformat()

        init_db(db_path)
        voo_price = _get_voo_price()
        if not voo_price or voo_price <= 0:
            return {}

        conn = get_connection(db_path)
        try:
            deposit_made = False
            row = conn.execute(
                "SELECT voo_shares, total_deposited FROM benchmark_account WHERE id=1"
            ).fetchone()

            if row is None:
                # First run: invest $10,000 at current VOO price
                voo_shares = INITIAL_DEPOSIT / voo_price
                total_deposited = INITIAL_DEPOSIT
                conn.execute(
                    "INSERT INTO benchmark_account (id, voo_shares, total_deposited) VALUES (1, ?, ?)",
                    (voo_shares, total_deposited),
                )
                conn.commit()
            else:
                voo_shares = row["voo_shares"]
                total_deposited = row["total_deposited"]

                # Monday deposit — idempotent via snapshot date check
                is_monday = today.weekday() == 0
                already_snapped = conn.execute(
                    "SELECT 1 FROM benchmark_snapshots WHERE date=?", (today_str,)
                ).fetchone()

                if is_monday and not already_snapped:
                    new_shares = WEEKLY_DEPOSIT / voo_price
                    voo_shares += new_shares
                    total_deposited += WEEKLY_DEPOSIT
                    conn.execute(
                        "UPDATE benchmark_account SET voo_shares=?, total_deposited=? WHERE id=1",
                        (voo_shares, total_deposited),
                    )
                    conn.commit()
                    deposit_made = True

            # Upsert daily snapshot
            total_value = voo_shares * voo_price
            conn.execute(
                """INSERT INTO benchmark_snapshots
                       (date, voo_shares, voo_price, total_value, total_deposited)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(date) DO UPDATE SET
                       voo_shares=excluded.voo_shares,
                       voo_price=excluded.voo_price,
                       total_value=excluded.total_value,
                       total_deposited=excluded.total_deposited""",
                (today_str, voo_shares, voo_price, total_value, total_deposited),
            )
            conn.commit()

            return {
                "voo_shares": voo_shares,
                "voo_price": voo_price,
                "total_value": total_value,
                "total_deposited": total_deposited,
                "deposit_made": deposit_made,
            }
        finally:
            conn.close()

    except Exception as exc:
        print(f"[benchmark] update_benchmark error: {exc}")
        return {}


def _get_voo_price() -> float | None:
    """Fetch current VOO price via yfinance. Returns None on any failure."""
    try:
        import yfinance as yf
        price = yf.Ticker("VOO").fast_info["last_price"]
        if price and float(price) > 0:
            return float(price)
        return None
    except Exception:
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_benchmark.py -v
```

Expected: 5 PASS

- [ ] **Step 5: Run full suite**

```bash
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

Expected: 82 passed (77 + 5 new).

- [ ] **Step 6: Commit**

```bash
git add agent/tools/benchmark.py tests/test_benchmark.py
git commit -m "feat(FEAT-002): add benchmark.py with update_benchmark and VOO price fetch"
```

---

## Task 3: Integrate benchmark into `cmd_run2()` in `main.py`

**Files:**
- Modify: `agent/main.py`
- Test: `tests/test_main.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_main.py`:

```python
# FEAT-002
def test_cmd_run2_monday_deposit_adds_100_to_agent_cash(tmp_path, monkeypatch, capsys):
    """On Monday, cmd_run2 adds $100 to agent cash (idempotent — only once per day)."""
    db_file = str(tmp_path / "portfolio.db")
    plan_file = str(tmp_path / "run1_plan.json")
    out_file = str(tmp_path / "output" / "dashboard.html")

    init_db(db_file)

    plan = {
        "decisions": {
            "trades": [],
            "skip_new_buys": False,
            "briefing": "ok",
            "market_education": {},
            "daily_lesson": {},
        }
    }
    with open(plan_file, "w") as f:
        json.dump(plan, f)

    # Patch date.today() to return a Monday
    from datetime import date as _date_cls
    class _FakeDate(_date_cls):
        @classmethod
        def today(cls):
            return cls(2026, 4, 20)  # Monday

    monkeypatch.setattr("agent.main.date", _FakeDate)
    monkeypatch.setattr("agent.tools.notify.send_telegram", lambda msg: True)
    monkeypatch.setattr("agent.tools.benchmark._get_voo_price", lambda: 450.0)

    from agent.portfolio.engine import get_portfolio_status
    initial_cash = get_portfolio_status(db_file)["cash"]

    cmd_run2(db_path=db_file, plan_path=plan_file, output_path=out_file)

    final_cash = get_portfolio_status(db_file)["cash"]
    assert abs(final_cash - (initial_cash + 100.0)) < 0.01
```

- [ ] **Step 2: Run test to verify it fails**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_main.py::test_cmd_run2_monday_deposit_adds_100_to_agent_cash -v
```

Expected: FAIL

- [ ] **Step 3: Update imports in `agent/main.py`**

Change the existing database import line from:
```python
from agent.portfolio.database import DB_PATH, init_db
```
To:
```python
from agent.portfolio.database import DB_PATH, get_connection, init_db  # FEAT-002: added get_connection
```

Add to the imports block (near the other tool imports):
```python
from agent.tools.benchmark import update_benchmark  # FEAT-002
```

- [ ] **Step 4: Add Monday deposit + benchmark call to `cmd_run2()`**

Inside `cmd_run2()`, immediately after `init_db(db_path)`, add:

```python
        # FEAT-002: Monday $100 deposit into agent cash — idempotent via benchmark_snapshots
        if date.today().weekday() == 0:
            _today_str = date.today().isoformat()
            _dep_conn = get_connection(db_path)
            try:
                _already = _dep_conn.execute(
                    "SELECT 1 FROM benchmark_snapshots WHERE date=?", (_today_str,)
                ).fetchone()
                if not _already:
                    _dep_conn.execute("UPDATE account SET cash = cash + 100.0 WHERE id = 1")
                    _dep_conn.commit()
                    print("Monday deposit: +$100 added to agent cash")
            finally:
                _dep_conn.close()
```

Then find the existing `notify_run2(executed, rejected, portfolio)` call and replace it with:

```python
        benchmark = update_benchmark(db_path)  # FEAT-002
        notify_run2(executed, rejected, portfolio, benchmark=benchmark)  # FEAT-002
```

- [ ] **Step 5: Run test to verify it passes**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_main.py::test_cmd_run2_monday_deposit_adds_100_to_agent_cash -v
```

Expected: PASS

- [ ] **Step 6: Run full suite**

```bash
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

Expected: 83 passed.

- [ ] **Step 7: Commit**

```bash
git add agent/main.py
git commit -m "feat(FEAT-002): add Monday agent deposit and benchmark call in cmd_run2"
```

---

## Task 4: Extend `notify_run2()` with benchmark block

**Files:**
- Modify: `agent/tools/notify.py` (`notify_run2` signature + body)
- Test: `tests/test_notify.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_notify.py`:

```python
# FEAT-002
def test_notify_run2_includes_benchmark_block(monkeypatch):
    """notify_run2 appends benchmark comparison when data is present."""
    sent = []
    monkeypatch.setattr("agent.tools.notify.send_telegram", lambda msg: sent.append(msg) or True)

    from agent.tools.notify import notify_run2
    notify_run2(
        executed=[],
        rejected=[],
        portfolio={"cash": 5000.0, "total_value": 10200.0, "pnl_pct": 2.0},
        benchmark={
            "voo_shares": 22.5,
            "voo_price": 450.0,
            "total_value": 10350.0,
            "total_deposited": 10100.0,
            "deposit_made": True,
        },
    )

    assert len(sent) == 1
    msg = sent[0]
    assert "📊 Benchmark" in msg
    assert "VOO" in msg
    assert "10,350" in msg
    assert "+$100 deposited" in msg


# FEAT-002
def test_notify_run2_skips_benchmark_when_absent(monkeypatch):
    """notify_run2 sends normally when benchmark is not provided."""
    sent = []
    monkeypatch.setattr("agent.tools.notify.send_telegram", lambda msg: sent.append(msg) or True)

    from agent.tools.notify import notify_run2
    notify_run2(
        executed=[],
        rejected=[],
        portfolio={"cash": 5000.0, "total_value": 10200.0, "pnl_pct": 2.0},
    )

    assert len(sent) == 1
    assert "📊 Benchmark" not in sent[0]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_notify.py::test_notify_run2_includes_benchmark_block tests/test_notify.py::test_notify_run2_skips_benchmark_when_absent -v
```

Expected: FAIL — `TypeError: notify_run2() got an unexpected keyword argument 'benchmark'`

- [ ] **Step 3: Update `notify_run2()` in `agent/tools/notify.py`**

Replace the entire `notify_run2` function:

```python
def notify_run2(  # FEAT-002: added benchmark param
    executed: list[str],
    rejected: list[str],
    portfolio: dict,
    benchmark: dict | None = None,
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
        agent_sign = "+" if agent_pnl >= 0 else ""
        voo_sign = "+" if voo_pnl >= 0 else ""
        lines.append("")
        lines.append("<b>📊 Benchmark (VOO buy &amp; hold):</b>")
        lines.append(f"  Agent: ${total:,.0f} ({agent_sign}{agent_pnl:.1f}%)")
        lines.append(f"  VOO:   ${voo_total:,.0f} ({voo_sign}{voo_pnl:.1f}%)")
        lines.append(f"  Deposited: ${deposited:,.0f} each")
        if benchmark.get("deposit_made"):
            lines.append("  +$100 deposited to both today")

    send_telegram("\n".join(lines))
```

- [ ] **Step 4: Run new tests to verify they pass**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_notify.py::test_notify_run2_includes_benchmark_block tests/test_notify.py::test_notify_run2_skips_benchmark_when_absent -v
```

Expected: 2 PASS

- [ ] **Step 5: Run full suite**

```bash
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

Expected: 85 passed.

- [ ] **Step 6: Commit**

```bash
git add agent/tools/notify.py tests/test_notify.py
git commit -m "feat(FEAT-002): extend notify_run2 with benchmark comparison block"
```

---

## Task 5: Extend dashboard with benchmark section

**Files:**
- Modify: `agent/tools/dashboard.py`
- Test: `tests/test_dashboard.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_dashboard.py`:

```python
# FEAT-002
def test_dashboard_includes_benchmark_section_when_data_present(tmp_path):
    """Dashboard shows 'vs VOO' section when benchmark_snapshots has data."""
    from agent.portfolio.database import get_connection
    db = _db(tmp_path)
    conn = get_connection(db)
    conn.execute(
        "INSERT INTO benchmark_account (id, voo_shares, total_deposited) VALUES (1, 22.5, 10000.0)"
    )
    conn.execute(
        "INSERT INTO benchmark_snapshots (date, voo_shares, voo_price, total_value, total_deposited) "
        "VALUES ('2026-04-16', 22.5, 450.0, 10125.0, 10000.0)"
    )
    conn.commit()
    conn.close()

    out = _out(tmp_path)
    generate_dashboard(db_path=db, output_path=out)
    html = open(out, encoding="utf-8").read()
    assert "vs VOO" in html
    assert "10,125" in html


# FEAT-002
def test_dashboard_no_benchmark_section_when_no_data(tmp_path):
    """Dashboard renders normally with no benchmark data — no crash, no VOO section."""
    db = _db(tmp_path)
    out = _out(tmp_path)
    generate_dashboard(db_path=db, output_path=out)
    html = open(out, encoding="utf-8").read()
    assert "Investment Portfolio Dashboard" in html
    assert "vs VOO" not in html
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_dashboard.py::test_dashboard_includes_benchmark_section_when_data_present tests/test_dashboard.py::test_dashboard_no_benchmark_section_when_no_data -v
```

Expected: FAIL — `assert "vs VOO" in html`

- [ ] **Step 3: Move Chart.js CDN to `<head>` in `dashboard.py`**

In `_build_html()`, find the `chart_html` block. Remove `<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>` from inside `chart_html` — it currently appears inside the `if snapshots:` block. After the removal, `chart_html` should only contain the `<div class="chart-container">` and the `<script>(function() { ... })();</script>`.

Then add the CDN to the `<head>` section of the HTML template (the `html = f"""<!DOCTYPE html>...` string), inside `<head>`:

```html
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
```

Place it just before `</head>`.

- [ ] **Step 4: Add benchmark data query to `_build_html()`**

In `_build_html()`, inside the `conn = get_connection(db_path)` block, after the `snapshots` query, add:

```python
        # FEAT-002: benchmark snapshots for comparison chart
        bench_rows = conn.execute(
            "SELECT date, total_value, total_deposited FROM benchmark_snapshots "
            "ORDER BY date DESC LIMIT 30"
        ).fetchall()
        bench_snapshots = list(reversed([
            {"date": r["date"], "total_value": r["total_value"],
             "total_deposited": r["total_deposited"]}
            for r in bench_rows
        ]))
        bench_latest = conn.execute(
            "SELECT total_value, total_deposited FROM benchmark_snapshots "
            "ORDER BY date DESC LIMIT 1"
        ).fetchone()
```

- [ ] **Step 5: Build benchmark HTML blocks**

After the existing `chart_html` block (after the `else: chart_html = ...` line), add:

```python
    # FEAT-002: benchmark comparison section
    if bench_latest:
        voo_total = bench_latest["total_value"]
        voo_deposited = bench_latest["total_deposited"]
        voo_pnl_dollar = voo_total - voo_deposited
        voo_pnl_pct = (voo_pnl_dollar / voo_deposited * 100) if voo_deposited else 0.0
        voo_color = "#2ecc71" if voo_pnl_dollar >= 0 else "#e74c3c"
        delta = total_value - voo_total
        delta_color = "#2ecc71" if delta >= 0 else "#e74c3c"
        delta_sign = "+" if delta >= 0 else ""

        # Comparison chart
        if bench_snapshots and snapshots:
            all_dates = sorted(
                set(s["date"] for s in snapshots) | set(s["date"] for s in bench_snapshots)
            )
            agent_by_date = {s["date"]: s["total_value"] for s in snapshots}
            voo_by_date = {s["date"]: s["total_value"] for s in bench_snapshots}
            cmp_labels = json.dumps(all_dates)
            cmp_agent = json.dumps([agent_by_date.get(d) for d in all_dates])
            cmp_voo = json.dumps([voo_by_date.get(d) for d in all_dates])
            comparison_chart_html = f"""
        <div class="chart-container">
            <canvas id="comparisonChart"></canvas>
        </div>
        <script>
        (function() {{
            const ctx = document.getElementById('comparisonChart').getContext('2d');
            new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels: {cmp_labels},
                    datasets: [
                        {{
                            label: 'Agent',
                            data: {cmp_agent},
                            borderColor: '#3498db',
                            backgroundColor: 'rgba(52,152,219,0.1)',
                            borderWidth: 2, pointRadius: 3, fill: true, tension: 0.3, spanGaps: true,
                        }},
                        {{
                            label: 'VOO (buy & hold)',
                            data: {cmp_voo},
                            borderColor: '#f39c12',
                            backgroundColor: 'rgba(243,156,18,0.1)',
                            borderWidth: 2, pointRadius: 3, fill: true, tension: 0.3, spanGaps: true,
                        }}
                    ]
                }},
                options: {{
                    responsive: true,
                    plugins: {{
                        title: {{ display: true, text: 'Agent vs VOO Performance',
                                   color: '#ecf0f1', font: {{ size: 16 }} }},
                        legend: {{ labels: {{ color: '#bdc3c7' }} }}
                    }},
                    scales: {{
                        x: {{ ticks: {{ color: '#bdc3c7' }}, grid: {{ color: '#2c3e50' }} }},
                        y: {{ ticks: {{ color: '#bdc3c7',
                                        callback: v => '$' + v.toLocaleString() }},
                              grid: {{ color: '#2c3e50' }} }}
                    }}
                }}
            }});
        }})();
        </script>"""
        else:
            comparison_chart_html = '<p class="empty-msg">Run for a few days to see the comparison chart</p>'

        benchmark_section_html = f"""
<section>
    <h2>vs VOO Benchmark</h2>
    <div class="summary-grid">
        <div class="stat-card">
            <div class="stat-label">Agent Value</div>
            <div class="stat-value" style="color:{pnl_color};">{fmt_dollar(total_value)}</div>
            <div style="font-size:0.85rem;color:{pnl_color};">{fmt_pnl(pnl_dollar, pnl_pct)}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">VOO Value</div>
            <div class="stat-value" style="color:{voo_color};">{fmt_dollar(voo_total)}</div>
            <div style="font-size:0.85rem;color:{voo_color};">{fmt_pnl(voo_pnl_dollar, voo_pnl_pct)}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Agent vs VOO</div>
            <div class="stat-value" style="color:{delta_color};">{delta_sign}{fmt_dollar(delta)}</div>
            <div style="font-size:0.85rem;color:#95a5a6;">Deposited: {fmt_dollar(voo_deposited)} each</div>
        </div>
    </div>
    {comparison_chart_html}
</section>"""
    else:
        benchmark_section_html = ""
```

- [ ] **Step 6: Inject `benchmark_section_html` into the HTML template**

In the `html = f"""..."""` template string, add `{benchmark_section_html}` just before the existing `<section>` for "Open Positions":

```html
{benchmark_section_html}

<section>
    <h2>Open Positions</h2>
```

- [ ] **Step 7: Run new tests to verify they pass**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_dashboard.py::test_dashboard_includes_benchmark_section_when_data_present tests/test_dashboard.py::test_dashboard_no_benchmark_section_when_no_data -v
```

Expected: 2 PASS

- [ ] **Step 8: Run full suite**

```bash
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

Expected: 87 passed.

- [ ] **Step 9: Commit**

```bash
git add agent/tools/dashboard.py tests/test_dashboard.py
git commit -m "feat(FEAT-002): add VOO benchmark section and comparison chart to dashboard"
```
