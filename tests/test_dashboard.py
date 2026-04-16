"""Tests for agent/tools/dashboard.py — HTML dashboard generator."""

import os
import pytest

from agent.portfolio.database import init_db
from agent.portfolio.engine import execute_buy, execute_sell, save_daily_snapshot
from agent.tools.dashboard import generate_dashboard


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _db(tmp_path):
    """Return a fresh database path under tmp_path."""
    db = str(tmp_path / "portfolio.db")
    init_db(db)
    return db


def _out(tmp_path, name="dashboard.html"):
    return str(tmp_path / "output" / name)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_generate_dashboard_creates_file(tmp_path):
    db = _db(tmp_path)
    out = _out(tmp_path)
    generate_dashboard(db_path=db, output_path=out)
    assert os.path.exists(out)


def test_dashboard_html_contains_sections(tmp_path):
    db = _db(tmp_path)
    execute_buy("AAPL", 5, 150.0, "test buy", db_path=db)
    save_daily_snapshot("2024-01-01", 10500.0, 9250.0, 5.0, db_path=db)
    out = _out(tmp_path)
    generate_dashboard(db_path=db, output_path=out)
    html = open(out, encoding="utf-8").read()
    assert "Total Portfolio Value" in html
    assert "Open Positions" in html
    assert "Trade History" in html
    assert "30-Day" in html


def test_dashboard_empty_portfolio(tmp_path):
    db = _db(tmp_path)
    out = _out(tmp_path)
    generate_dashboard(db_path=db, output_path=out)
    html = open(out, encoding="utf-8").read()
    assert "No open positions" in html


def test_dashboard_no_trades(tmp_path):
    db = _db(tmp_path)
    out = _out(tmp_path)
    generate_dashboard(db_path=db, output_path=out)
    html = open(out, encoding="utf-8").read()
    assert "No trades yet" in html


def test_generate_dashboard_returns_path(tmp_path):
    db = _db(tmp_path)
    out = _out(tmp_path)
    result = generate_dashboard(db_path=db, output_path=out)
    assert result == out


def test_generate_dashboard_creates_output_dir(tmp_path):
    db = _db(tmp_path)
    # Use a deeply nested non-existent directory
    out = str(tmp_path / "nested" / "deep" / "dashboard.html")
    result = generate_dashboard(db_path=db, output_path=out)
    assert os.path.exists(out)
    assert result == out


def test_dashboard_shows_total_value(tmp_path):
    db = _db(tmp_path)
    # Buy 10 shares at $100 → invested = $1,000; cash remaining = $9,000
    execute_buy("TSLA", 10, 100.0, "test", db_path=db)
    out = _out(tmp_path)
    generate_dashboard(db_path=db, output_path=out)
    html = open(out, encoding="utf-8").read()
    # Total value = 9000 + 1000 = $10,000
    assert "$10,000.00" in html


def test_dashboard_includes_chartjs(tmp_path):
    db = _db(tmp_path)
    save_daily_snapshot("2024-01-01", 10000.0, 10000.0, 0.0, db_path=db)
    out = _out(tmp_path)
    generate_dashboard(db_path=db, output_path=out)
    html = open(out, encoding="utf-8").read().lower()
    assert "chart.js" in html or "cdn.jsdelivr.net" in html
