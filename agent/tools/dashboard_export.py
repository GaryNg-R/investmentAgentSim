"""
Produces the versioned data.json consumed by the Vue 3 dashboard.

Public surface:
    SCHEMA_VERSION  — integer bumped on breaking schema changes
    export_dashboard_data(db_path, plan_path, output_path) — reads DB + plan,
        writes data.json atomically, returns the built dict (never raises).
"""

import json
import math
import os
import random
import string
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from agent.portfolio.database import get_connection
from agent.portfolio.engine import STARTING_CASH
from agent.tools.stock_data import get_price

SCHEMA_VERSION = 1

_ET = ZoneInfo("America/New_York")


def _build_account_section(db_path: str) -> dict:
    conn = get_connection(db_path)
    try:
        cash = conn.execute("SELECT cash FROM account WHERE id=1").fetchone()[0]
        snap = conn.execute(
            "SELECT total_value FROM daily_snapshots ORDER BY date DESC LIMIT 1"
        ).fetchone()
        total_value = snap[0] if snap else cash
        bmark = conn.execute(
            "SELECT total_deposited FROM benchmark_account WHERE id=1"
        ).fetchone()
        bsnap = conn.execute(
            "SELECT total_value FROM benchmark_snapshots ORDER BY date DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()

    voo_total = bsnap[0] if bsnap else None
    profit_dollars = total_value - STARTING_CASH
    profit_percent = (profit_dollars / STARTING_CASH) * 100.0
    vs_voo_dollars = (total_value - voo_total) if voo_total else None
    vs_voo_percent = ((total_value / voo_total - 1.0) * 100.0) if voo_total else None

    return {
        "total_value": total_value,
        "cash": cash,
        "starting_cash": STARTING_CASH,
        "profit_dollars": profit_dollars,
        "profit_percent": profit_percent,
        "vs_voo_dollars": vs_voo_dollars,
        "vs_voo_percent": vs_voo_percent,
    }


def _build_positions_section(db_path: str) -> list:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT ticker, shares, avg_cost FROM positions"
        ).fetchall()
        cash = conn.execute("SELECT cash FROM account WHERE id=1").fetchone()[0]
    finally:
        conn.close()

    raw = []
    total_market_value = 0.0
    for row in rows:
        ticker, shares, avg_cost = row["ticker"], row["shares"], row["avg_cost"]
        try:
            current_price = get_price(ticker)
        except Exception:
            current_price = None
        market_value = shares * current_price if current_price is not None else None
        if market_value is not None:
            total_market_value += market_value
        raw.append((ticker, shares, avg_cost, current_price, market_value))

    total_portfolio = total_market_value + cash
    positions = []
    for ticker, shares, avg_cost, current_price, market_value in raw:
        if current_price is None:
            positions.append({
                "ticker": ticker,
                "shares": shares,
                "avg_cost": avg_cost,
                "current_price": None,
                "market_value": None,
                "profit_dollars": None,
                "profit_percent": None,
                "portfolio_pct": None,
            })
        else:
            cost_basis = shares * avg_cost
            profit_dollars = market_value - cost_basis
            profit_percent = (profit_dollars / cost_basis) * 100.0
            portfolio_pct = (market_value / total_portfolio * 100.0) if total_portfolio else None
            positions.append({
                "ticker": ticker,
                "shares": shares,
                "avg_cost": avg_cost,
                "current_price": current_price,
                "market_value": market_value,
                "profit_dollars": profit_dollars,
                "profit_percent": profit_percent,
                "portfolio_pct": portfolio_pct,
            })
    return positions


def _build_allocation_section(positions_list: list, cash: float) -> list:
    valid = [(p["ticker"], p["market_value"]) for p in positions_list if p["market_value"] is not None]
    total = sum(mv for _, mv in valid) + cash
    if total == 0:
        return []

    entries = []
    for ticker, mv in sorted(valid, key=lambda x: x[1], reverse=True):
        entries.append({"label": ticker, "pct": round(mv / total * 100.0, 1)})
    cash_pct = round(cash / total * 100.0, 1)
    # Adjust cash entry so rounding sums exactly to 100.0
    current_sum = sum(e["pct"] for e in entries) + cash_pct
    cash_pct = round(cash_pct + round(100.0 - current_sum, 1), 1)
    entries.append({"label": "Cash", "pct": cash_pct})
    return entries


def _build_snapshots_section(db_path: str) -> list:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT date, total_value, cash, pnl_pct FROM daily_snapshots ORDER BY date ASC"
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "date": r["date"],
            "total_value": r["total_value"],
            "cash": r["cash"],
            "profit_percent": r["pnl_pct"],
        }
        for r in rows
    ]


def _build_benchmark_section(db_path: str) -> dict:
    conn = get_connection(db_path)
    try:
        acct = conn.execute(
            "SELECT voo_shares, total_deposited FROM benchmark_account WHERE id=1"
        ).fetchone()
        latest = conn.execute(
            "SELECT voo_price, total_value FROM benchmark_snapshots ORDER BY date DESC LIMIT 1"
        ).fetchone()
        snaps = conn.execute(
            "SELECT date, voo_shares, voo_price, total_value FROM benchmark_snapshots ORDER BY date ASC"
        ).fetchall()
    finally:
        conn.close()

    return {
        "voo_shares": acct["voo_shares"] if acct else None,
        "voo_price": latest["voo_price"] if latest else None,
        "total_value": latest["total_value"] if latest else None,
        "total_deposited": acct["total_deposited"] if acct else None,
        "snapshots": [
            {
                "date": s["date"],
                "voo_shares": s["voo_shares"],
                "voo_price": s["voo_price"],
                "total_value": s["total_value"],
            }
            for s in snaps
        ],
    }


def _build_trades_section(db_path: str) -> list:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT id, timestamp, action, ticker, shares, price, total, reasoning "
            "FROM trades ORDER BY timestamp ASC, id ASC"
        ).fetchall()
    finally:
        conn.close()

    # FIFO buy queues per ticker: list of [remaining_shares, price_per_share]
    buy_queues: dict = {}
    result = []
    for r in rows:
        ticker = r["ticker"]
        action = r["action"]
        shares = r["shares"]
        total = r["total"]
        reasoning = r["reasoning"] or ""

        if action == "BUY":
            buy_queues.setdefault(ticker, []).append([shares, r["price"]])
            realized_profit = None
        else:
            queue = buy_queues.get(ticker, [])
            remaining = shares
            cost_basis = 0.0
            while remaining > 0 and queue:
                head_shares, head_price = queue[0]
                take = min(remaining, head_shares)
                cost_basis += take * head_price
                head_shares -= take
                remaining -= take
                if head_shares == 0:
                    queue.pop(0)
                else:
                    queue[0][0] = head_shares
            realized_profit = (total - cost_basis) if remaining == 0 else None

        result.append({
            "id": r["id"],
            "timestamp": r["timestamp"],
            "action": action,
            "ticker": ticker,
            "shares": shares,
            "price": r["price"],
            "total": total,
            "reasoning": reasoning,
            "realized_profit": realized_profit,
        })

    result.reverse()
    return result


def _build_today_plan_section(plan_path: str):
    try:
        with open(plan_path) as f:
            data = json.load(f)
        decisions = data.get("decisions", {})
        return {
            "decisions": decisions.get("trades", []),
            "skip_new_buys": decisions.get("skip_new_buys"),
            "market_direction": data.get("market_direction"),
            "briefing": decisions.get("briefing"),
        }
    except Exception:
        return None


def _build_education_section(plan_path: str) -> dict:
    try:
        with open(plan_path) as f:
            data = json.load(f)
        decisions = data.get("decisions", {})
        return {
            "market_education": decisions.get("market_education"),
            "daily_lesson": decisions.get("daily_lesson"),
        }
    except Exception:
        return {"market_education": None, "daily_lesson": None}


def _build_stats_section(trades_list: list, snapshots_list: list) -> dict:
    closed = [t for t in trades_list if t["action"] == "SELL" and t.get("realized_profit") is not None]
    winners = [t for t in closed if t["realized_profit"] > 0]
    losers = [t for t in closed if t["realized_profit"] <= 0]

    win_rate = (len(winners) / len(closed) * 100.0) if closed else None
    avg_winner = (sum(t["realized_profit"] for t in winners) / len(winners)) if winners else None
    avg_loser = (sum(t["realized_profit"] for t in losers) / len(losers)) if losers else None
    total_realized = sum(t["realized_profit"] for t in closed) if closed else 0.0

    best = max(closed, key=lambda t: t["realized_profit"]) if closed else None
    worst = min(closed, key=lambda t: t["realized_profit"]) if closed else None

    per_ticker: dict = {}
    for t in closed:
        per_ticker[t["ticker"]] = per_ticker.get(t["ticker"], 0.0) + t["realized_profit"]

    values = [s["total_value"] for s in snapshots_list]
    if len(values) >= 2:
        peak = values[0]
        max_dd = 0.0
        for v in values[1:]:
            if v > peak:
                peak = v
            dd = (peak - v) / peak * 100.0 if peak else 0.0
            if dd > max_dd:
                max_dd = dd
        changes = [(values[i] / values[i - 1] - 1.0) * 100.0 for i in range(1, len(values))]
        mean = sum(changes) / len(changes)
        variance = sum((c - mean) ** 2 for c in changes) / len(changes)
        volatility = math.sqrt(variance)
    else:
        max_dd = None
        volatility = None

    return {
        "win_rate": win_rate,
        "winners_count": len(winners),
        "losers_count": len(losers),
        "avg_winner": avg_winner,
        "avg_loser": avg_loser,
        "best_trade": {"ticker": best["ticker"], "realized_profit": best["realized_profit"]} if best else None,
        "worst_trade": {"ticker": worst["ticker"], "realized_profit": worst["realized_profit"]} if worst else None,
        "max_drawdown_percent": max_dd,
        "daily_volatility": volatility,
        "total_realized_profit": total_realized,
        "per_ticker_realized": per_ticker,
    }


def _build_dividends_section(db_path: str) -> list:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT date, ticker, shares_held, div_per_share, shares_added "
            "FROM dividend_events ORDER BY date DESC"
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "date": r["date"],
            "ticker": r["ticker"],
            "shares_held": r["shares_held"],
            "div_per_share": r["div_per_share"],
            "shares_added": r["shares_added"],
        }
        for r in rows
    ]


def _write_atomic(data: dict, output_path: str) -> None:
    dir_ = os.path.dirname(output_path)
    if dir_:
        os.makedirs(dir_, exist_ok=True)
    tmp = output_path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, output_path)


def export_dashboard_data(db_path: str, plan_path: str, output_path: str) -> dict:
    """Build and atomically write data.json. Never raises."""
    try:
        positions = _build_positions_section(db_path)
        conn = get_connection(db_path)
        try:
            cash = conn.execute("SELECT cash FROM account WHERE id=1").fetchone()[0]
        finally:
            conn.close()

        trades = _build_trades_section(db_path)
        snapshots = _build_snapshots_section(db_path)

        run_id = (
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
            + "_"
            + "".join(random.choices(string.hexdigits[:16], k=6))
        )
        payload = {
            "metadata": {
                "schema_version": SCHEMA_VERSION,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "date_et": datetime.now(_ET).strftime("%Y-%m-%d"),
                "run_id": run_id,
            },
            "account": _build_account_section(db_path),
            "positions": positions,
            "allocation": _build_allocation_section(positions, cash),
            "snapshots": snapshots,
            "benchmark": _build_benchmark_section(db_path),
            "trades": trades,
            "today_plan": _build_today_plan_section(plan_path),
            "education": _build_education_section(plan_path),
            "stats": _build_stats_section(trades, snapshots),
            "dividends": _build_dividends_section(db_path),
        }
        _write_atomic(payload, output_path)
        return payload
    except Exception as exc:
        err = {"metadata": {"schema_version": SCHEMA_VERSION}, "error": str(exc)}
        try:
            _write_atomic(err, output_path)
        except Exception:
            pass
        return err
