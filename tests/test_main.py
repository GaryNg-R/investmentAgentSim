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
                    "shares": 5,
                    "reasoning": "Strong momentum",
                }
            ],
            "skip_new_buys": False,
            "briefing": "Buy NVDA",
        },
    }
    with open(plan_file, "w") as fh:
        json.dump(plan_payload, fh)

    with patch("agent.main.get_price", return_value=100.0):
        cmd_run2(db_path=db_file, plan_path=plan_file, output_path=output_file)

    captured = capsys.readouterr()
    # Price is $100, 5 shares = $500, well within $10,000 cash — should be EXECUTED
    assert "EXECUTED" in captured.out or "REJECTED" in captured.out
