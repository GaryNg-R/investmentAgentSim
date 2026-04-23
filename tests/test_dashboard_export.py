"""Tests for agent/tools/dashboard_export.py — pure logic, no external calls."""

import json
import os
import sqlite3

import pytest

from agent.tools.dashboard_export import (
    SCHEMA_VERSION,
    _build_account_section,
    _build_allocation_section,
    _build_benchmark_section,
    _build_dividends_section,
    _build_education_section,
    _build_positions_section,
    _build_snapshots_section,
    _build_stats_section,
    _build_today_plan_section,
    _build_trades_section,
    export_dashboard_data,
)
from tests.fixtures.dashboard_export_seed import seed_known_database


# ---------------------------------------------------------------------------
# Task 2: Skeleton
# ---------------------------------------------------------------------------

def test_schema_version_is_1():
    assert SCHEMA_VERSION == 1


def test_export_dashboard_data_is_callable():
    assert callable(export_dashboard_data)


# ---------------------------------------------------------------------------
# Task 3: Account summary
# ---------------------------------------------------------------------------

def test_account_section(tmp_path):
    db = str(tmp_path / "test.db")
    seed_known_database(db)
    result = _build_account_section(db)

    assert set(result.keys()) == {
        "total_value", "cash", "starting_cash",
        "profit_dollars", "profit_percent",
        "vs_voo_dollars", "vs_voo_percent",
    }
    assert abs(result["cash"] - 5238.89) < 0.01
    assert abs(result["starting_cash"] - 10000.0) < 0.01
    # Most recent snapshot total_value = 10409.92
    assert abs(result["total_value"] - 10409.92) < 0.01
    assert abs(result["profit_dollars"] - 409.92) < 0.01
    assert abs(result["profit_percent"] - 4.0992) < 0.01
    # voo total from latest benchmark_snapshot = 10095.06
    assert abs(result["vs_voo_dollars"] - (10409.92 - 10095.06)) < 0.02
    assert result["vs_voo_percent"] is not None


def test_account_section_no_snapshots(tmp_path):
    """When no snapshots exist, total_value falls back to cash."""
    from agent.portfolio.database import init_db
    db = str(tmp_path / "empty.db")
    init_db(db)
    result = _build_account_section(db)
    assert abs(result["total_value"] - result["cash"]) < 0.01


# ---------------------------------------------------------------------------
# Task 4: Positions with current prices
# ---------------------------------------------------------------------------

def test_positions_happy_path(tmp_path, monkeypatch):
    db = str(tmp_path / "test.db")
    seed_known_database(db)
    prices = {"META": 681.0, "COIN": 193.0, "TSLA": 402.0}
    monkeypatch.setattr("agent.tools.dashboard_export.get_price", lambda t: prices[t])

    result = _build_positions_section(db)
    assert len(result) == 3
    for p in result:
        assert set(p.keys()) == {
            "ticker", "shares", "avg_cost", "current_price",
            "market_value", "profit_dollars", "profit_percent", "portfolio_pct",
        }
        assert p["current_price"] is not None
        assert p["market_value"] is not None

    meta = next(p for p in result if p["ticker"] == "META")
    # 3 shares * 681 = 2043; cost = 3 * 674.16 = 2022.48; profit = 20.52
    assert abs(meta["market_value"] - 2043.0) < 0.01
    assert abs(meta["profit_dollars"] - 20.52) < 0.01

    # All portfolio_pct values sum to < 100 (cash not included in positions)
    total_pct = sum(p["portfolio_pct"] for p in result)
    assert total_pct < 100.0


def test_positions_price_fetch_failure(tmp_path, monkeypatch):
    db = str(tmp_path / "test.db")
    seed_known_database(db)

    def mock_price(ticker):
        if ticker == "TSLA":
            raise RuntimeError("fetch failed")
        return {"META": 681.0, "COIN": 193.0}[ticker]

    monkeypatch.setattr("agent.tools.dashboard_export.get_price", mock_price)

    result = _build_positions_section(db)
    tsla = next(p for p in result if p["ticker"] == "TSLA")
    assert tsla["current_price"] is None
    assert tsla["market_value"] is None
    assert tsla["profit_dollars"] is None
    assert tsla["profit_percent"] is None
    assert tsla["portfolio_pct"] is None

    meta = next(p for p in result if p["ticker"] == "META")
    assert meta["current_price"] == 681.0


# ---------------------------------------------------------------------------
# Task 5: Allocation breakdown
# ---------------------------------------------------------------------------

def test_allocation_sums_to_100(tmp_path, monkeypatch):
    db = str(tmp_path / "test.db")
    seed_known_database(db)
    prices = {"META": 681.0, "COIN": 193.0, "TSLA": 402.0}
    monkeypatch.setattr("agent.tools.dashboard_export.get_price", lambda t: prices[t])

    positions = _build_positions_section(db)
    alloc = _build_allocation_section(positions, cash=5238.89)

    assert len(alloc) == 4  # 3 positions + Cash
    assert alloc[-1]["label"] == "Cash"
    total = sum(e["pct"] for e in alloc)
    assert abs(total - 100.0) < 0.01


def test_allocation_excludes_failed_price(tmp_path, monkeypatch):
    db = str(tmp_path / "test.db")
    seed_known_database(db)

    def mock_price(ticker):
        if ticker == "TSLA":
            raise RuntimeError("fetch failed")
        return {"META": 681.0, "COIN": 193.0}[ticker]

    monkeypatch.setattr("agent.tools.dashboard_export.get_price", mock_price)

    positions = _build_positions_section(db)
    alloc = _build_allocation_section(positions, cash=5238.89)
    labels = [e["label"] for e in alloc]
    assert "TSLA" not in labels
    assert abs(sum(e["pct"] for e in alloc) - 100.0) < 0.01


# ---------------------------------------------------------------------------
# Task 6: Snapshots and benchmark series
# ---------------------------------------------------------------------------

def test_snapshots_section(tmp_path):
    db = str(tmp_path / "test.db")
    seed_known_database(db)
    snaps = _build_snapshots_section(db)

    assert len(snaps) == 5
    dates = [s["date"] for s in snaps]
    assert dates == sorted(dates)
    assert set(snaps[0].keys()) == {"date", "total_value", "cash", "profit_percent"}
    assert abs(snaps[-1]["total_value"] - 10409.92) < 0.01


def test_benchmark_section(tmp_path):
    db = str(tmp_path / "test.db")
    seed_known_database(db)
    bmark = _build_benchmark_section(db)

    assert set(bmark.keys()) == {"voo_shares", "voo_price", "total_value", "total_deposited", "snapshots"}
    assert abs(bmark["voo_shares"] - 15.507) < 0.001
    assert abs(bmark["voo_price"] - 651.00) < 0.01  # most recent
    assert len(bmark["snapshots"]) == 3
    dates = [s["date"] for s in bmark["snapshots"]]
    assert dates == sorted(dates)


# ---------------------------------------------------------------------------
# Task 7: Trade history with FIFO realized profit
# ---------------------------------------------------------------------------

def test_trades_section_fifo(tmp_path):
    db = str(tmp_path / "test.db")
    seed_known_database(db)
    trades = _build_trades_section(db)

    assert len(trades) == 7
    # Newest first
    assert trades[0]["timestamp"] > trades[-1]["timestamp"]

    # MSTR sell: buy 17@143.69 (total=2442.73), sell 17@168.86 (total=2870.62)
    # realized = 2870.62 - 2442.73 = 427.89
    mstr_sell = next(t for t in trades if t["ticker"] == "MSTR" and t["action"] == "SELL")
    assert abs(mstr_sell["realized_profit"] - 427.89) < 0.02

    # TSLA sell: buy 6@388.37 (total=2330.22), sell 6@385.375 (total=2312.25)
    # realized = 2312.25 - 2330.22 = -17.97
    tsla_sell = next(t for t in trades if t["ticker"] == "TSLA" and t["action"] == "SELL")
    assert abs(tsla_sell["realized_profit"] - (-17.97)) < 0.02

    # All BUY rows have realized_profit = None
    for t in trades:
        if t["action"] == "BUY":
            assert t["realized_profit"] is None

    # reasoning is always a string
    for t in trades:
        assert isinstance(t["reasoning"], str)


# ---------------------------------------------------------------------------
# Task 8: Today's plan
# ---------------------------------------------------------------------------

def test_today_plan_happy_path(tmp_path):
    plan = {
        "market_direction": "risk_on",
        "decisions": {
            "trades": [{"action": "BUY", "ticker": "AAPL", "shares": 5, "reasoning": "good"}],
            "skip_new_buys": False,
            "briefing": "All good.",
        },
    }
    plan_path = str(tmp_path / "plan.json")
    with open(plan_path, "w") as f:
        json.dump(plan, f)

    result = _build_today_plan_section(plan_path)
    assert result is not None
    assert result["market_direction"] == "risk_on"
    assert result["skip_new_buys"] is False
    assert result["briefing"] == "All good."
    assert len(result["decisions"]) == 1


def test_today_plan_missing_file(tmp_path):
    result = _build_today_plan_section(str(tmp_path / "nonexistent.json"))
    assert result is None


def test_today_plan_malformed_file(tmp_path):
    plan_path = str(tmp_path / "bad.json")
    with open(plan_path, "w") as f:
        f.write("not valid json }{")
    result = _build_today_plan_section(plan_path)
    assert result is None


# ---------------------------------------------------------------------------
# Task 9: Daily education
# ---------------------------------------------------------------------------

def test_education_happy_path(tmp_path):
    plan = {
        "market_direction": "risk_on",
        "decisions": {
            "trades": [],
            "market_education": {"summary_en": "Up day", "summary_zh": "涨", "sources": []},
            "daily_lesson": {"term": "RSI", "explanation_en": "Momentum", "explanation_zh": "动量"},
        },
    }
    plan_path = str(tmp_path / "plan.json")
    with open(plan_path, "w") as f:
        json.dump(plan, f)

    result = _build_education_section(plan_path)
    assert result["market_education"]["summary_en"] == "Up day"
    assert result["daily_lesson"]["term"] == "RSI"


def test_education_absent_fields(tmp_path):
    plan = {"market_direction": "neutral", "decisions": {"trades": []}}
    plan_path = str(tmp_path / "plan.json")
    with open(plan_path, "w") as f:
        json.dump(plan, f)

    result = _build_education_section(plan_path)
    assert result["market_education"] is None
    assert result["daily_lesson"] is None


def test_education_missing_file(tmp_path):
    result = _build_education_section(str(tmp_path / "nope.json"))
    assert result["market_education"] is None
    assert result["daily_lesson"] is None


# ---------------------------------------------------------------------------
# Task 10: Derived trade statistics
# ---------------------------------------------------------------------------

def test_stats_section(tmp_path):
    db = str(tmp_path / "test.db")
    seed_known_database(db)
    trades = _build_trades_section(db)
    snaps = _build_snapshots_section(db)
    stats = _build_stats_section(trades, snaps)

    # 2 closed round trips: MSTR winner (+427.89), TSLA loser (-17.97)
    assert stats["winners_count"] == 1
    assert stats["losers_count"] == 1
    assert abs(stats["win_rate"] - 50.0) < 0.01
    assert abs(stats["avg_winner"] - 427.89) < 0.02
    assert abs(stats["avg_loser"] - (-17.97)) < 0.02
    assert stats["best_trade"]["ticker"] == "MSTR"
    assert stats["worst_trade"]["ticker"] == "TSLA"
    assert abs(stats["total_realized_profit"] - (427.89 - 17.97)) < 0.02
    assert "MSTR" in stats["per_ticker_realized"]
    assert "TSLA" in stats["per_ticker_realized"]

    # Drawdown: peak=10250, trough=10409.92 — wait, values are:
    # [10050, 10200, 10180, 10250, 10409.92]
    # peaks: 10050 → 10200 → 10200 → 10250 → 10409.92
    # drawdowns: (10200-10180)/10200 = 0.196%
    assert stats["max_drawdown_percent"] is not None
    assert stats["max_drawdown_percent"] > 0

    assert stats["daily_volatility"] is not None


def test_stats_no_closed_trades(tmp_path):
    snaps = [
        {"total_value": 10000.0, "date": "2026-04-16"},
        {"total_value": 10100.0, "date": "2026-04-17"},
    ]
    trades = [
        {"action": "BUY", "ticker": "AAPL", "shares": 5, "realized_profit": None},
    ]
    stats = _build_stats_section(trades, snaps)
    assert stats["win_rate"] is None
    assert stats["winners_count"] == 0
    assert stats["total_realized_profit"] == 0.0


# ---------------------------------------------------------------------------
# Task 11: Dividend events
# ---------------------------------------------------------------------------

def test_dividends_section(tmp_path):
    db = str(tmp_path / "test.db")
    seed_known_database(db)
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            "INSERT INTO dividend_events (date, ticker, account, shares_held, div_per_share, shares_added) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("2026-04-21", "META", "agent", 3.0, 0.52, 0.00228),
        )
        conn.execute(
            "INSERT INTO dividend_events (date, ticker, account, shares_held, div_per_share, shares_added) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("2026-04-18", "COIN", "agent", 12.0, 0.10, 0.00060),
        )
        conn.commit()
    finally:
        conn.close()

    result = _build_dividends_section(db)
    assert len(result) == 2
    # Descending date order
    assert result[0]["date"] == "2026-04-21"
    assert result[1]["date"] == "2026-04-18"
    assert set(result[0].keys()) == {"date", "ticker", "shares_held", "div_per_share", "shares_added"}


def test_dividends_empty(tmp_path):
    from agent.portfolio.database import init_db
    db = str(tmp_path / "empty.db")
    init_db(db)
    assert _build_dividends_section(db) == []


# ---------------------------------------------------------------------------
# Task 12: Full export + atomic write
# ---------------------------------------------------------------------------

def test_export_happy_path(tmp_path, monkeypatch):
    db = str(tmp_path / "test.db")
    seed_known_database(db)
    prices = {"META": 681.0, "COIN": 193.0, "TSLA": 402.0}
    monkeypatch.setattr("agent.tools.dashboard_export.get_price", lambda t: prices[t])

    plan = {
        "market_direction": "risk_on",
        "decisions": {
            "trades": [{"action": "BUY", "ticker": "AAPL", "shares": 3, "reasoning": "good"}],
            "skip_new_buys": False,
            "briefing": "Go time.",
            "market_education": {"summary_en": "Up", "summary_zh": "涨", "sources": []},
            "daily_lesson": {"term": "RSI", "explanation_en": "...", "explanation_zh": "..."},
        },
    }
    plan_path = str(tmp_path / "plan.json")
    with open(plan_path, "w") as f:
        json.dump(plan, f)

    output = str(tmp_path / "out" / "data.json")
    result = export_dashboard_data(db, plan_path, output)

    assert os.path.exists(output)
    with open(output) as f:
        loaded = json.load(f)

    expected_keys = {
        "metadata", "account", "positions", "allocation",
        "snapshots", "benchmark", "trades", "today_plan",
        "education", "stats", "dividends",
    }
    assert set(loaded.keys()) == expected_keys
    assert loaded["metadata"]["schema_version"] == 1
    assert "generated_at" in loaded["metadata"]
    assert "date_et" in loaded["metadata"]
    assert "run_id" in loaded["metadata"]
    assert loaded == result


def test_export_atomic_write_on_error(tmp_path, monkeypatch):
    """If assembly fails mid-way, the previous file at output_path is not clobbered."""
    from agent.portfolio.database import init_db
    db = str(tmp_path / "test.db")
    init_db(db)

    output = str(tmp_path / "data.json")
    sentinel = json.dumps({"sentinel": True})
    with open(output, "w") as f:
        f.write(sentinel)

    # Patch one internal function to raise
    monkeypatch.setattr(
        "agent.tools.dashboard_export._build_account_section",
        lambda db_path: (_ for _ in ()).throw(RuntimeError("simulated crash")),
    )

    result = export_dashboard_data(db, str(tmp_path / "plan.json"), output)
    # Function must not raise
    assert isinstance(result, dict)
    # Output file should exist and contain the error JSON (atomically replaced)
    with open(output) as f:
        content = json.load(f)
    assert "error" in content


def test_export_broken_db_path(tmp_path):
    output = str(tmp_path / "data.json")
    result = export_dashboard_data("/nonexistent/path/db.sqlite", "/nope/plan.json", output)
    assert isinstance(result, dict)
    assert "error" in result
    assert os.path.exists(output)
    with open(output) as f:
        content = json.load(f)
    assert "error" in content
