import sqlite3
import pytest

from agent.portfolio.database import get_connection, init_db


def test_tables_created(tmp_path):
    """init_db creates all 4 tables."""
    db_path = str(tmp_path / "portfolio.db")
    init_db(db_path)

    conn = get_connection(db_path)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = {row["name"] for row in cursor.fetchall()}
    conn.close()

    assert "account" in tables
    assert "positions" in tables
    assert "trades" in tables
    assert "daily_snapshots" in tables


def test_initial_cash_seeded(tmp_path):
    """Account row id=1 has cash=10000.0 after init."""
    db_path = str(tmp_path / "portfolio.db")
    init_db(db_path)

    conn = get_connection(db_path)
    row = conn.execute("SELECT cash FROM account WHERE id=1").fetchone()
    conn.close()

    assert row is not None
    assert row["cash"] == 10000.0


def test_init_idempotent(tmp_path):
    """Calling init_db twice does not raise or duplicate the seed row."""
    db_path = str(tmp_path / "portfolio.db")

    init_db(db_path)
    init_db(db_path)  # must not raise

    conn = get_connection(db_path)
    rows = conn.execute("SELECT * FROM account WHERE id=1").fetchall()
    conn.close()

    assert len(rows) == 1
    assert rows[0]["cash"] == 10000.0


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
