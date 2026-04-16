"""Tests for agent/portfolio/engine.py"""

import pytest

from agent.portfolio.database import init_db
from agent.portfolio.engine import (
    execute_buy,
    execute_sell,
    get_portfolio_status,
    get_trade_history,
    save_daily_snapshot,
)


@pytest.fixture
def db(tmp_path):
    """Return a fresh DB path with schema + seed data."""
    db_path = str(tmp_path / "test_portfolio.db")
    init_db(db_path)
    return db_path


# ---------------------------------------------------------------------------
# 1. Initial state
# ---------------------------------------------------------------------------

def test_initial_status(db):
    status = get_portfolio_status(db)
    assert status["cash"] == 10_000.0
    assert status["positions"] == []
    assert status["pnl_dollar"] == 0.0
    assert status["pnl_pct"] == 0.0
    assert status["position_count"] == 0
    assert status["total_invested"] == 0.0
    assert status["total_value"] == 10_000.0


# ---------------------------------------------------------------------------
# 2. Basic buy
# ---------------------------------------------------------------------------

def test_execute_buy(db):
    status = execute_buy("NVDA", 5, 100.0, "test buy", db_path=db)
    assert status["cash"] == pytest.approx(9_500.0)
    assert status["position_count"] == 1
    pos = status["positions"][0]
    assert pos["ticker"] == "NVDA"
    assert pos["shares"] == 5
    assert pos["avg_cost"] == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# 3. Weighted average cost on second buy
# ---------------------------------------------------------------------------

def test_execute_buy_weighted_avg(db):
    execute_buy("NVDA", 5, 100.0, "first buy", db_path=db)
    status = execute_buy("NVDA", 5, 120.0, "second buy", db_path=db)

    assert status["cash"] == pytest.approx(10_000.0 - 5 * 100.0 - 5 * 120.0)
    assert status["position_count"] == 1
    pos = status["positions"][0]
    assert pos["shares"] == 10
    # weighted avg: (5*100 + 5*120) / 10 = 110
    assert pos["avg_cost"] == pytest.approx(110.0)


# ---------------------------------------------------------------------------
# 4. Buy then full sell → position removed, cash restored
# ---------------------------------------------------------------------------

def test_execute_sell(db):
    execute_buy("NVDA", 5, 100.0, "buy", db_path=db)
    status = execute_sell("NVDA", 5, 100.0, "sell", db_path=db)

    assert status["cash"] == pytest.approx(10_000.0)
    assert status["position_count"] == 0
    assert status["positions"] == []


# ---------------------------------------------------------------------------
# 5. Partial sell
# ---------------------------------------------------------------------------

def test_execute_sell_partial(db):
    execute_buy("NVDA", 10, 100.0, "buy", db_path=db)
    status = execute_sell("NVDA", 4, 100.0, "partial sell", db_path=db)

    assert status["position_count"] == 1
    pos = status["positions"][0]
    assert pos["ticker"] == "NVDA"
    assert pos["shares"] == 6


# ---------------------------------------------------------------------------
# 6. Insufficient cash raises ValueError
# ---------------------------------------------------------------------------

def test_insufficient_cash(db):
    with pytest.raises(ValueError, match="Insufficient cash"):
        execute_buy("NVDA", 200, 100.0, "too big", db_path=db)  # $20 000 > $10 000


# ---------------------------------------------------------------------------
# 7. Selling unowned stock raises ValueError
# ---------------------------------------------------------------------------

def test_sell_no_position(db):
    with pytest.raises(ValueError, match="No position held"):
        execute_sell("TSLA", 1, 200.0, "no position", db_path=db)


# ---------------------------------------------------------------------------
# 8. Daily snapshot: saved and idempotent (INSERT OR REPLACE)
# ---------------------------------------------------------------------------

def test_save_daily_snapshot(db):
    from agent.portfolio.database import get_connection

    save_daily_snapshot("2026-04-14", 10_500.0, 9_000.0, 5.0, db_path=db)

    conn = get_connection(db)
    row = conn.execute(
        "SELECT * FROM daily_snapshots WHERE date='2026-04-14'"
    ).fetchone()
    conn.close()
    assert row is not None
    assert row["total_value"] == pytest.approx(10_500.0)
    assert row["cash"] == pytest.approx(9_000.0)
    assert row["pnl_pct"] == pytest.approx(5.0)

    # Replace with updated values — must not raise and must overwrite
    save_daily_snapshot("2026-04-14", 10_600.0, 9_100.0, 6.0, db_path=db)

    conn = get_connection(db)
    rows = conn.execute(
        "SELECT * FROM daily_snapshots WHERE date='2026-04-14'"
    ).fetchall()
    conn.close()
    assert len(rows) == 1  # still only one row
    assert rows[0]["total_value"] == pytest.approx(10_600.0)
