# VOO Benchmark Comparison — Design Spec

**Date:** 2026-04-16
**Status:** Approved

---

## Goal

Track a parallel "VOO buy & hold" paper account alongside the AI agent, so the user can see whether the agent actually beats passive index investing. Both accounts start with $10,000, and $100 is added every Monday to each.

---

## Scope

Five files change:
- `agent/portfolio/database.py` — two new tables
- `agent/tools/benchmark.py` — new file, core logic
- `agent/main.py` — call `update_benchmark()` in run2, pass result to notify
- `agent/tools/notify.py` — extend `notify_run2()` with benchmark block
- `agent/tools/dashboard.py` — add comparison summary bar + chart

---

## Design

### 1. Database (`agent/portfolio/database.py`)

Two new tables appended to the existing `_DDL` string:

```sql
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

`benchmark_account` holds a single row (id=1) representing the live state of the VOO account. `benchmark_snapshots` holds one row per date for the comparison chart.

### 2. `agent/tools/benchmark.py` (new file)

Single public function:

```python
def update_benchmark(db_path: str = DB_PATH) -> dict:
```

Logic on every call:
1. Init tables if not present (calls `init_db`)
2. Fetch current VOO price via `yfinance.Ticker("VOO").fast_info["last_price"]`
3. If `benchmark_account` has no row (first run): seed with `$10,000 / voo_price` shares, `total_deposited = 10000.0`
4. If today is Monday (`datetime.today().weekday() == 0`) AND today's date not already in `benchmark_snapshots`: add `$100 / voo_price` shares, increment `total_deposited` by 100
5. Save/update today's row in `benchmark_snapshots`
6. Return status dict

Return dict:
```python
{
    "voo_shares": float,
    "voo_price": float,
    "total_value": float,       # voo_shares * voo_price
    "total_deposited": float,
    "deposit_made": bool        # True if a Monday $100 deposit happened this call
}
```

Never raises — returns `{}` on any error so run2 is never blocked.

### 3. `agent/main.py` — run2 integration

At end of `cmd_run2()`, after `generate_dashboard()`:

```python
from agent.tools.benchmark import update_benchmark  # FEAT-002

benchmark = update_benchmark(db_path)  # FEAT-002
notify_run2(executed, rejected, portfolio, benchmark=benchmark)
```

Also update the weekly $100 agent cash deposit on Mondays:

```python
# FEAT-002: Monday $100 deposit into agent cash
if datetime.today().weekday() == 0:
    conn = get_connection(db_path)
    conn.execute("UPDATE account SET cash = cash + 100 WHERE id = 1")
    conn.commit()
    conn.close()
```

### 4. `agent/tools/notify.py` — extend `notify_run2()`

Add `benchmark: dict | None = None` parameter. When truthy, append after the portfolio line:

```
📊 Benchmark comparison:
  Agent:  $9,982 (-0.18%) | VOO: $10,368 (+3.68%)
  Deposited: $10,300 each
  [Monday only: +$100 deposited to both today]
```

P&L % calculated as `(total_value - total_deposited) / total_deposited * 100`.

Silently skip block if `benchmark` is empty.

### 5. `agent/tools/dashboard.py` — comparison UI

Two additions to `_build_html()`:

**a) Summary bar** (inserted above existing content):
```
Agent: $9,982 (-0.18%)  |  VOO: $10,368 (+3.68%)  |  Deposited: $10,300
```
Colour-coded: green if agent > VOO, red if agent < VOO.

**b) Comparison chart** — new Chart.js line chart:
- Dataset 1 (blue): agent `total_value` from `daily_snapshots`
- Dataset 2 (orange): VOO `total_value` from `benchmark_snapshots`
- X-axis: date, Y-axis: dollar value
- Rendered as a second `<canvas>` below the existing charts

Both datasets queried from the same `portfolio.db`.

---

## Weekly Deposit Rules

| Account | Amount | When | How |
|---------|--------|------|-----|
| Agent | $100 cash | Every Monday run2 | `UPDATE account SET cash = cash + 100` |
| VOO | $100 → fractional shares | Every Monday run2 | `$100 / voo_price` shares added |

Monday detection: `datetime.today().weekday() == 0`. Idempotent — deposit only applies once per date (checked via `benchmark_snapshots` date row).

---

## What Does NOT Change

- Run 1 (`cmd_run1`) — unchanged
- Monitor (`cmd_monitor`) — unchanged
- All existing tests — must continue to pass
- No new dependencies (yfinance already installed)

---

## Success Criteria

- First run seeds VOO account with $10,000 at current VOO price
- Every Monday run2 adds $100 to both accounts
- Telegram run2 message shows agent vs VOO value + % return
- Dashboard shows comparison summary bar and dual-line chart
- Agent never fails or errors if VOO price fetch fails
- All existing tests pass
