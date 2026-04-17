"""weekly_report.py — Build weekly performance summary from SQLite data.  # FEAT-004
Queries the past Mon–Sun week and returns a structured dict for notify_weekly().
Never raises — returns a zeroed dict on any error.
"""

from __future__ import annotations

from datetime import date, timedelta

from agent.portfolio.database import DB_PATH, get_connection, init_db


def build_weekly_report(db_path: str = DB_PATH, today: date | None = None) -> dict:  # FEAT-004
    """
    Build a weekly performance report for the Mon–Sun week containing `today`.
    Returns a dict with week bounds, trades, agent P&L, VOO P&L, best/worst ticker.
    Returns zeroed dict on any error.
    """
    try:
        today = today or date.today()
        # Monday of this week
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)  # Sunday

        init_db(db_path)
        conn = get_connection(db_path)
        try:
            # Trades this week
            trade_rows = conn.execute(
                "SELECT action, ticker, shares, price, total, timestamp "
                "FROM trades "
                "WHERE date(timestamp) BETWEEN ? AND ? "
                "ORDER BY timestamp",
                (week_start.isoformat(), week_end.isoformat()),
            ).fetchall()
            trades = [
                {
                    "action": r["action"],
                    "ticker": r["ticker"],
                    "shares": r["shares"],
                    "price": r["price"],
                    "total": r["total"],
                    "timestamp": r["timestamp"],
                }
                for r in trade_rows
            ]

            # Agent P&L: earliest and latest snapshot in window
            snap_start = conn.execute(
                "SELECT total_value FROM daily_snapshots "
                "WHERE date >= ? ORDER BY date ASC LIMIT 1",
                (week_start.isoformat(),),
            ).fetchone()
            snap_end = conn.execute(
                "SELECT total_value FROM daily_snapshots "
                "WHERE date <= ? ORDER BY date DESC LIMIT 1",
                (week_end.isoformat(),),
            ).fetchone()
            agent_start = snap_start["total_value"] if snap_start else 0.0
            agent_end = snap_end["total_value"] if snap_end else 0.0
            agent_pnl_dollar = agent_end - agent_start
            agent_pnl_pct = (agent_pnl_dollar / agent_start * 100) if agent_start else 0.0

            # VOO P&L: same approach from benchmark_snapshots
            voo_start_row = conn.execute(
                "SELECT total_value FROM benchmark_snapshots "
                "WHERE date >= ? ORDER BY date ASC LIMIT 1",
                (week_start.isoformat(),),
            ).fetchone()
            voo_end_row = conn.execute(
                "SELECT total_value FROM benchmark_snapshots "
                "WHERE date <= ? ORDER BY date DESC LIMIT 1",
                (week_end.isoformat(),),
            ).fetchone()
            voo_start = voo_start_row["total_value"] if voo_start_row else 0.0
            voo_end = voo_end_row["total_value"] if voo_end_row else 0.0
            voo_pnl_dollar = voo_end - voo_start
            voo_pnl_pct = (voo_pnl_dollar / voo_start * 100) if voo_start else 0.0

            # Best/worst ticker by P&L this week (from positions + trades)
            pos_rows = conn.execute(
                "SELECT ticker, shares, avg_cost FROM positions"
            ).fetchall()
            best_ticker = None
            worst_ticker = None
            if pos_rows:
                best_pnl = None
                worst_pnl = None
                for p in pos_rows:
                    from agent.tools.stock_data import get_price
                    price = get_price(p["ticker"])
                    if price is None:
                        continue
                    pnl = (price - p["avg_cost"]) / p["avg_cost"] * 100
                    if best_pnl is None or pnl > best_pnl:
                        best_pnl = pnl
                        best_ticker = p["ticker"]
                    if worst_pnl is None or pnl < worst_pnl:
                        worst_pnl = pnl
                        worst_ticker = p["ticker"]

            return {
                "week_start": week_start.isoformat(),
                "week_end": week_end.isoformat(),
                "trades": trades,
                "agent_start_value": agent_start,
                "agent_end_value": agent_end,
                "agent_pnl_dollar": agent_pnl_dollar,
                "agent_pnl_pct": agent_pnl_pct,
                "voo_start_value": voo_start,
                "voo_end_value": voo_end,
                "voo_pnl_dollar": voo_pnl_dollar,
                "voo_pnl_pct": voo_pnl_pct,
                "best_ticker": best_ticker,
                "worst_ticker": worst_ticker,
            }
        finally:
            conn.close()

    except Exception as exc:
        print(f"[weekly_report] build_weekly_report error: {exc}")
        return {
            "week_start": "", "week_end": "", "trades": [],
            "agent_start_value": 0.0, "agent_end_value": 0.0,
            "agent_pnl_dollar": 0.0, "agent_pnl_pct": 0.0,
            "voo_start_value": 0.0, "voo_end_value": 0.0,
            "voo_pnl_dollar": 0.0, "voo_pnl_pct": 0.0,
            "best_ticker": None, "worst_ticker": None,
        }
