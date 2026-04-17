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


def test_process_dividends_skips_zero_dividend(tmp_path, monkeypatch):
    """Skips silently when div_per_share is 0.0 (suspended/corrected dividend)."""
    db = _db(tmp_path)
    execute_buy("NVDA", 10, 100.0, "test", db_path=db)

    monkeypatch.setattr("agent.tools.dividends._get_dividend_today", lambda ticker, today: 0.0)
    monkeypatch.setattr("agent.tools.dividends._get_current_price", lambda ticker: 100.0)

    result = process_dividends(db, _today=date(2026, 4, 17))
    assert result == []

    # Shares unchanged
    conn = get_connection(db)
    row = conn.execute("SELECT shares FROM positions WHERE ticker='NVDA'").fetchone()
    conn.close()
    assert abs(row["shares"] - 10.0) < 1e-6
