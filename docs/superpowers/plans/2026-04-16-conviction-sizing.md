# Conviction-Based Position Sizing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Claude labels each BUY trade with a conviction level (high/medium/low); the agent converts that into a dollar amount (high=15%, medium=8%, low=4% of available cash) and calculates shares from the current price.

**Architecture:** Three-layer change — (1) prompt updated so Claude emits `"conviction"` on BUY trades instead of `"shares"`, (2) new `position_size_from_conviction()` helper in `risk_rules.py`, (3) `cmd_run2` in `main.py` uses conviction to calculate shares before calling `validate_buy`/`execute_buy`. SELL trades are unchanged — Claude still specifies `"shares"` to sell.

**Tech Stack:** Python 3.12, existing SQLite/yfinance stack, no new dependencies.

---

## File Map

| File | Change |
|------|--------|
| `agent/claude_agent.py` | Update prompt: BUY trades use `conviction` not `shares`; update `parse_decisions` to pass `conviction` through |
| `agent/tools/risk_rules.py` | Add `position_size_from_conviction(conviction, cash)` |
| `agent/main.py` | `cmd_run2`: for BUY trades, derive `shares` from conviction + price |
| `tests/test_risk_rules.py` | Add 4 tests for `position_size_from_conviction` |
| `tests/test_claude_agent.py` | Add 2 tests: conviction parsed on BUY, missing conviction defaults to medium |
| `tests/test_main.py` | Add 1 test: high-conviction BUY allocates ~15% of cash |

---

## Task 1: Add `position_size_from_conviction()` to `risk_rules.py`

**Files:**
- Modify: `agent/tools/risk_rules.py`
- Test: `tests/test_risk_rules.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_risk_rules.py` (after the existing imports, add `position_size_from_conviction` to the import line first):

```python
from agent.tools.risk_rules import (
    MAX_POSITION_PCT,
    MAX_POSITIONS,
    PROFIT_TARGET_PCT,
    STOP_LOSS_PCT,
    check_profit_target,
    check_stop_loss,
    position_size_from_conviction,
    validate_buy,
    validate_sell,
)
```

Then add the tests:

```python
class TestConvictionSizing:
    def test_high_conviction_is_15_pct_of_cash(self):
        assert abs(position_size_from_conviction("high", 10_000.0) - 1_500.0) < 0.01

    def test_medium_conviction_is_8_pct_of_cash(self):
        assert abs(position_size_from_conviction("medium", 10_000.0) - 800.0) < 0.01

    def test_low_conviction_is_4_pct_of_cash(self):
        assert abs(position_size_from_conviction("low", 10_000.0) - 400.0) < 0.01

    def test_unknown_conviction_defaults_to_medium(self):
        assert abs(position_size_from_conviction("unknown", 10_000.0) - 800.0) < 0.01
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_risk_rules.py::TestConvictionSizing -v
```

Expected: FAIL — `ImportError: cannot import name 'position_size_from_conviction'`

- [ ] **Step 3: Add `position_size_from_conviction` to `agent/tools/risk_rules.py`**

Add these constants near the top of the file (after existing constants):

```python
CONVICTION_PCT = {"high": 0.15, "medium": 0.08, "low": 0.04}
```

Then add the function (after existing constants, before `validate_buy`):

```python
def position_size_from_conviction(conviction: str, cash: float) -> float:
    """Return dollar amount to invest based on conviction level and available cash."""
    pct = CONVICTION_PCT.get(conviction, CONVICTION_PCT["medium"])
    return cash * pct
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_risk_rules.py::TestConvictionSizing -v
```

Expected: 4 PASS

- [ ] **Step 5: Run full suite**

```bash
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

Expected: all existing tests + 4 new = passing.

- [ ] **Step 6: Commit**

```bash
git add agent/tools/risk_rules.py tests/test_risk_rules.py
git commit -m "feat(FEAT-003): add position_size_from_conviction to risk_rules"
```

---

## Task 2: Update Claude prompt and `parse_decisions` for conviction

**Files:**
- Modify: `agent/claude_agent.py`
- Test: `tests/test_claude_agent.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_claude_agent.py`:

```python
# FEAT-003
def test_parse_decisions_passes_conviction_through():
    """conviction field on BUY trades is preserved in parsed output."""
    raw = """<decisions>
{
  "trades": [
    {"action": "BUY", "ticker": "NVDA", "conviction": "high", "reasoning": "strong momentum"}
  ],
  "skip_new_buys": false,
  "briefing": "Buy NVDA.",
  "market_education": {},
  "daily_lesson": {}
}
</decisions>"""
    decisions = parse_decisions(raw)
    assert decisions["trades"][0]["conviction"] == "high"


# FEAT-003
def test_parse_decisions_buy_without_conviction_still_parses():
    """BUY trade without conviction field parses fine — conviction defaults handled in cmd_run2."""
    raw = """<decisions>
{
  "trades": [
    {"action": "BUY", "ticker": "AAPL", "reasoning": "solid pick"}
  ],
  "skip_new_buys": false,
  "briefing": "Buy AAPL.",
  "market_education": {},
  "daily_lesson": {}
}
</decisions>"""
    decisions = parse_decisions(raw)
    assert decisions["trades"][0].get("conviction") is None
```

- [ ] **Step 2: Run tests to verify they pass already**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_claude_agent.py::test_parse_decisions_passes_conviction_through tests/test_claude_agent.py::test_parse_decisions_buy_without_conviction_still_parses -v
```

Expected: PASS — `parse_decisions` already passes trades through as-is. If they pass, skip Step 3.

- [ ] **Step 3: Update the prompt in `build_prompt()` to tell Claude to use conviction**

In `agent/claude_agent.py`, find `section6` and replace the trades example line:

```python
# Old:
{"action": "BUY or SELL", "ticker": "TICKER", "shares": N, "reasoning": "one sentence"}

# New:
{"action": "BUY", "ticker": "TICKER", "conviction": "high or medium or low", "reasoning": "one sentence"},
{"action": "SELL", "ticker": "TICKER", "shares": N, "reasoning": "one sentence"}
```

Also add to the Rules block at the bottom of `section6`:

```
- BUY trades: include "conviction" (high/medium/low), do NOT include "shares" — the agent sizes the position
- SELL trades: include "shares" to sell (integer), do NOT include "conviction"
```

- [ ] **Step 4: Run full suite to confirm no regressions**

```bash
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

Expected: all passing.

- [ ] **Step 5: Commit**

```bash
git add agent/claude_agent.py tests/test_claude_agent.py
git commit -m "feat(FEAT-003): update Claude prompt to use conviction on BUY trades"
```

---

## Task 3: Use conviction sizing in `cmd_run2`

**Files:**
- Modify: `agent/main.py`
- Test: `tests/test_main.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_main.py`:

```python
# FEAT-003
def test_run2_high_conviction_buy_allocates_15pct_of_cash(tmp_path, monkeypatch, capsys):
    """High-conviction BUY allocates ~15% of available cash."""
    from datetime import datetime as _dt
    from zoneinfo import ZoneInfo
    db_file = str(tmp_path / "portfolio.db")
    plan_file = str(tmp_path / "run1_plan.json")
    output_file = str(tmp_path / "output" / "dashboard.html")

    init_db(db_file)

    plan_payload = {
        "decisions": {
            "trades": [
                {
                    "action": "BUY",
                    "ticker": "NVDA",
                    "conviction": "high",
                    "reasoning": "strong momentum",
                }
            ],
            "skip_new_buys": False,
            "briefing": "Buy NVDA high conviction.",
        }
    }
    with open(plan_file, "w") as fh:
        json.dump(plan_payload, fh)

    _market_open_et = _dt(2026, 4, 15, 10, 0, tzinfo=ZoneInfo("America/New_York"))
    monkeypatch.setattr("agent.tools.notify.send_telegram", lambda msg: True)
    monkeypatch.setattr("agent.tools.benchmark._get_voo_price", lambda: 450.0)

    with (
        patch("agent.main.get_price", return_value=100.0),
        patch("agent.main.datetime") as mock_dt,
    ):
        mock_dt.now.return_value = _market_open_et
        mock_dt.side_effect = lambda *a, **kw: __import__("datetime").datetime(*a, **kw)
        cmd_run2(db_path=db_file, plan_path=plan_file, output_path=output_file)

    captured = capsys.readouterr()
    # 15% of $10,000 = $1,500; at $100/share = 15 shares
    assert "EXECUTED: BUY 15.0 NVDA" in captured.out or "BUY 15" in captured.out
```

- [ ] **Step 2: Run test to verify it fails**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_main.py::test_run2_high_conviction_buy_allocates_15pct_of_cash -v
```

Expected: FAIL — trade either doesn't execute or uses wrong share count.

- [ ] **Step 3: Update imports in `agent/main.py`**

Add `position_size_from_conviction` to the risk_rules import:

```python
from agent.tools.risk_rules import (
    check_profit_target,
    check_stop_loss,
    position_size_from_conviction,
    validate_buy,
    validate_sell,
)
```

- [ ] **Step 4: Replace the BUY shares logic in `cmd_run2`**

In `agent/main.py`, find the BUY block inside `cmd_run2`. Replace:

```python
            if action == "BUY":
                if decisions.get("skip_new_buys", False):
                    print(f"Skipped BUY {ticker} (risk-off)")
                    continue
                valid, reason = validate_buy(ticker, shares, current_price, portfolio)
                if valid:
                    execute_buy(ticker, shares, current_price, reasoning, db_path)
                    msg = f"BUY {shares} {ticker} @ ${current_price:.2f}"
```

With:

```python
            if action == "BUY":
                if decisions.get("skip_new_buys", False):
                    print(f"Skipped BUY {ticker} (risk-off)")
                    continue
                # FEAT-003: derive shares from conviction + current price
                conviction = trade.get("conviction", "medium")
                dollar_amount = position_size_from_conviction(conviction, portfolio["cash"])
                shares = dollar_amount / current_price
                valid, reason = validate_buy(ticker, shares, current_price, portfolio)
                if valid:
                    execute_buy(ticker, shares, current_price, reasoning, db_path)
                    msg = f"BUY {shares} {ticker} @ ${current_price:.2f}"
```

- [ ] **Step 5: Run test to verify it passes**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_main.py::test_run2_high_conviction_buy_allocates_15pct_of_cash -v
```

Expected: PASS

- [ ] **Step 6: Run full suite**

```bash
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

Expected: all passing.

- [ ] **Step 7: Commit**

```bash
git add agent/main.py tests/test_main.py
git commit -m "feat(FEAT-003): derive BUY share count from conviction in cmd_run2"
```
