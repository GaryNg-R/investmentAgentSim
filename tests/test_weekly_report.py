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
