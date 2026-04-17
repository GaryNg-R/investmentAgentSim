"""Tests for agent/main.py CLI router."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from agent.portfolio.database import init_db
from agent.portfolio.engine import execute_buy
from agent.main import cmd_dashboard, cmd_history, cmd_monitor, cmd_run1, cmd_run2


# ---------------------------------------------------------------------------
# Test 1: Unknown command prints usage and exits with code 1
# ---------------------------------------------------------------------------

def test_unknown_command_exits_1():
    result = subprocess.run(
        [sys.executable, "-m", "agent.main", "badcommand"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "Usage:" in result.stdout or "Usage:" in result.stderr


# ---------------------------------------------------------------------------
# Test 2: No arguments prints usage and exits with code 1
# ---------------------------------------------------------------------------

def test_no_args_exits_1():
    result = subprocess.run(
        [sys.executable, "-m", "agent.main"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "Usage:" in result.stdout or "Usage:" in result.stderr


# ---------------------------------------------------------------------------
# Test 3: run2 without run1_plan.json exits with error message
# ---------------------------------------------------------------------------

def test_run2_missing_plan_exits_1(tmp_path, monkeypatch, capsys):
    db_file = str(tmp_path / "portfolio.db")
    plan_file = str(tmp_path / "nonexistent_plan.json")

    with pytest.raises(SystemExit) as exc_info:
        cmd_run2(db_path=db_file, plan_path=plan_file)

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "run1 plan not found" in captured.out or "run1 plan not found" in captured.err


# ---------------------------------------------------------------------------
# Test 4: history with empty DB prints "Total trades: 0"
# ---------------------------------------------------------------------------

def test_history_empty_db(tmp_path, monkeypatch, capsys):
    db_file = str(tmp_path / "portfolio.db")
    init_db(db_file)

    cmd_history(db_path=db_file)

    captured = capsys.readouterr()
    assert "Total trades: 0" in captured.out


# ---------------------------------------------------------------------------
# Test 5: monitor with no positions prints "No open positions"
# ---------------------------------------------------------------------------

def test_monitor_no_positions(tmp_path, monkeypatch, capsys):
    db_file = str(tmp_path / "portfolio.db")
    init_db(db_file)

    cmd_monitor(db_path=db_file, output_path=str(tmp_path / "dashboard.html"))

    captured = capsys.readouterr()
    assert "No open positions" in captured.out


# ---------------------------------------------------------------------------
# Test 6: dashboard command generates file and prints path
# ---------------------------------------------------------------------------

def test_dashboard_command(tmp_path, monkeypatch, capsys):
    db_file = str(tmp_path / "portfolio.db")
    output_file = str(tmp_path / "dashboard.html")
    init_db(db_file)

    cmd_dashboard(db_path=db_file, output_path=output_file)

    captured = capsys.readouterr()
    assert "Dashboard regenerated" in captured.out
    assert Path(output_file).exists()


# ---------------------------------------------------------------------------
# Test 7: run1 saves plan and prints briefing (mock run_analysis)
# ---------------------------------------------------------------------------

def test_run1_saves_plan(tmp_path, monkeypatch, capsys):
    db_file = str(tmp_path / "portfolio.db")
    plan_file = str(tmp_path / "run1_plan.json")

    mock_market = {
        "nasdaq_change_pct": 0.5,
        "sp500_change_pct": 0.3,
        "direction": "neutral",
        "summary": "Neutral market",
    }
    mock_stocks = [{"ticker": "NVDA", "score": 5, "price": 130.0, "rsi": 55.0, "signals": ["momentum"]}]
    mock_portfolio = {
        "cash": 10000.0,
        "positions": [],
        "total_value": 10000.0,
        "total_invested": 0.0,
        "pnl_dollar": 0.0,
        "pnl_pct": 0.0,
        "position_count": 0,
    }
    mock_decisions = {
        "trades": [],
        "skip_new_buys": False,
        "briefing": "Test briefing from mock Claude",
    }

    with (
        patch("agent.main.get_market_direction", return_value=mock_market),
        patch("agent.main.screen_stocks", return_value=mock_stocks),
        patch("agent.main.get_portfolio_status", return_value=mock_portfolio),
        patch("agent.main.run_analysis", return_value=mock_decisions),
    ):
        cmd_run1(db_path=db_file, plan_path=plan_file)

    captured = capsys.readouterr()
    assert "Test briefing from mock Claude" in captured.out
    assert f"Plan saved to {plan_file}" in captured.out


# ---------------------------------------------------------------------------
# Test 8: run2 executes a valid BUY and prints EXECUTED or REJECTED
# ---------------------------------------------------------------------------

def test_run2_executes_buy(tmp_path, monkeypatch, capsys):
    db_file = str(tmp_path / "portfolio.db")
    plan_file = str(tmp_path / "run1_plan.json")
    output_file = str(tmp_path / "dashboard.html")

    # Initialise DB
    init_db(db_file)

    # Write a plan with one BUY trade
    plan_payload = {
        "saved_at": "2026-04-15T00:00:00+00:00",
        "market_direction": "neutral",
        "decisions": {
            "trades": [
                {
                    "action": "BUY",
                    "ticker": "NVDA",
                    "conviction": "low",
                    "reasoning": "Strong momentum",
                }
            ],
            "skip_new_buys": False,
            "briefing": "Buy NVDA",
        },
    }
    with open(plan_file, "w") as fh:
        json.dump(plan_payload, fh)

    from datetime import datetime as _dt
    from zoneinfo import ZoneInfo
    _market_open_et = _dt(2026, 4, 15, 10, 0, tzinfo=ZoneInfo("America/New_York"))  # Tuesday 10am ET
    with (
        patch("agent.main.get_price", return_value=100.0),
        patch("agent.main.datetime") as mock_dt,
    ):
        mock_dt.now.return_value = _market_open_et
        mock_dt.side_effect = lambda *a, **kw: _dt(*a, **kw)
        cmd_run2(db_path=db_file, plan_path=plan_file, output_path=output_file)

    captured = capsys.readouterr()
    # Low conviction allocates 4% of $10,000 = $400; at $100/share = 4 shares — should be EXECUTED
    assert "EXECUTED: BUY 4 NVDA" in captured.out


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


def test_monitor_triggers_stop_loss(tmp_path, monkeypatch, capsys):
    """monitor should auto-sell a position that is down 10% (past -7% stop-loss threshold)."""
    from agent.portfolio.database import init_db
    from agent.portfolio.engine import execute_buy
    from agent.main import cmd_monitor

    db_file = str(tmp_path / "portfolio.db")
    init_db(db_file)
    # Buy 10 shares at $100 avg cost
    execute_buy("NVDA", 10, 100.0, "test buy", db_path=db_file)

    # Mock get_price to return $88 (12% below cost — past -7% stop-loss)
    monkeypatch.setattr("agent.main.get_price", lambda ticker: 88.0)

    cmd_monitor(db_path=db_file)
    captured = capsys.readouterr()
    assert "STOP-LOSS" in captured.out
    assert "NVDA" in captured.out


# FEAT-003
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
        mock_dt.side_effect = lambda *a, **kw: _dt(*a, **kw)
        cmd_run2(db_path=db_file, plan_path=plan_file, output_path=output_file)

    captured = capsys.readouterr()
    # 15% of $10,000 = $1,500; at $100/share = 15 shares
    assert "EXECUTED: BUY 15 NVDA" in captured.out
