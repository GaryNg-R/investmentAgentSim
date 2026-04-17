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


def test_generate_dashboard_never_raises_on_bad_db(tmp_path):
    """generate_dashboard must not raise even if the database path is invalid."""
    output_path = str(tmp_path / "dashboard.html")
    result = generate_dashboard(db_path="/nonexistent/path/db.sqlite", output_path=output_path)
    assert result == output_path
    assert os.path.exists(output_path)
    # Should write some HTML (even if it's the error page)
    with open(output_path) as f:
        content = f.read()
    assert "<html" in content.lower()
