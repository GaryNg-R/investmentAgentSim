"""Tests for agent/tools/benchmark.py — FEAT-002 VOO benchmark."""

from datetime import date

import pytest

from agent.portfolio.database import get_connection, init_db
from agent.tools.benchmark import update_benchmark


def _db(tmp_path):
    db = str(tmp_path / "portfolio.db")
    init_db(db)
    return db


# FEAT-002
def test_update_benchmark_seeds_on_first_run(tmp_path, monkeypatch):
    """First call seeds $10,000 into VOO at current price, no deposit flag."""
    monkeypatch.setattr("agent.tools.benchmark._get_voo_price", lambda: 450.0)
    db = _db(tmp_path)
    result = update_benchmark(db, _today=date(2026, 4, 16))  # Thursday
    assert result["voo_price"] == 450.0
    assert abs(result["voo_shares"] - 10000.0 / 450.0) < 0.0001
    assert result["total_deposited"] == 10000.0
    assert result["deposit_made"] is False
    assert abs(result["total_value"] - 10000.0) < 0.01


# FEAT-002
def test_update_benchmark_monday_deposit(tmp_path, monkeypatch):
    """Monday call adds $100 fractional shares and sets deposit_made=True."""
    monkeypatch.setattr("agent.tools.benchmark._get_voo_price", lambda: 450.0)
    db = _db(tmp_path)
    update_benchmark(db, _today=date(2026, 4, 16))  # Thursday — seed
    result = update_benchmark(db, _today=date(2026, 4, 20))  # Monday
    assert result["deposit_made"] is True
    assert result["total_deposited"] == 10100.0
    expected_shares = 10000.0 / 450.0 + 100.0 / 450.0
    assert abs(result["voo_shares"] - expected_shares) < 0.0001


# FEAT-002
def test_update_benchmark_non_monday_no_deposit(tmp_path, monkeypatch):
    """Non-Monday call does not deposit."""
    monkeypatch.setattr("agent.tools.benchmark._get_voo_price", lambda: 450.0)
    db = _db(tmp_path)
    update_benchmark(db, _today=date(2026, 4, 16))  # Thursday — seed
    result = update_benchmark(db, _today=date(2026, 4, 17))  # Friday
    assert result["deposit_made"] is False
    assert result["total_deposited"] == 10000.0


# FEAT-002
def test_update_benchmark_idempotent_same_monday(tmp_path, monkeypatch):
    """Calling twice on the same Monday only deposits once."""
    monkeypatch.setattr("agent.tools.benchmark._get_voo_price", lambda: 450.0)
    db = _db(tmp_path)
    monday = date(2026, 4, 13)
    update_benchmark(db, _today=date(2026, 4, 10))  # Friday — seed
    update_benchmark(db, _today=monday)              # First Monday call
    result2 = update_benchmark(db, _today=monday)   # Second Monday call — same day
    assert result2["total_deposited"] == 10100.0     # Only one $100 deposit
    assert result2["deposit_made"] is False          # Second call didn't deposit


# FEAT-002
def test_update_benchmark_returns_empty_on_price_failure(tmp_path, monkeypatch):
    """Returns {} without raising when VOO price cannot be fetched."""
    monkeypatch.setattr("agent.tools.benchmark._get_voo_price", lambda: None)
    db = _db(tmp_path)
    result = update_benchmark(db)
    assert result == {}
