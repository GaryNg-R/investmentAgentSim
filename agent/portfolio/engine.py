"""Portfolio engine: buy/sell execution, status, snapshots, and trade history."""

from .database import DB_PATH, get_connection, init_db

STARTING_CASH = 10_000.0


def get_portfolio_status(db_path=DB_PATH) -> dict:
    """
    Returns dict with:
    - cash: float
    - positions: list of dicts {ticker, shares, avg_cost}
    - total_invested: float (sum of shares * avg_cost for all positions)
    - total_value: float (cash + total_invested, since we don't have live prices here)
    - pnl_dollar: float (total_value - 10000.0)
    - pnl_pct: float
    - position_count: int
    """
    conn = get_connection(db_path)
    try:
        cash = conn.execute("SELECT cash FROM account WHERE id=1").fetchone()["cash"]
        rows = conn.execute("SELECT ticker, shares, avg_cost FROM positions").fetchall()
        positions = [{"ticker": r["ticker"], "shares": r["shares"], "avg_cost": r["avg_cost"]} for r in rows]
        total_invested = sum(p["shares"] * p["avg_cost"] for p in positions)
        total_value = cash + total_invested
        pnl_dollar = total_value - STARTING_CASH
        pnl_pct = (pnl_dollar / STARTING_CASH) * 100.0
        return {
            "cash": cash,
            "positions": positions,
            "total_invested": total_invested,
            "total_value": total_value,
            "pnl_dollar": pnl_dollar,
            "pnl_pct": pnl_pct,
            "position_count": len(positions),
        }
    finally:
        conn.close()


def execute_buy(ticker: str, shares: int, price: float, reasoning: str, db_path=DB_PATH) -> dict:
    """
    Executes a paper BUY. Atomic transaction.
    - Deducts shares*price from cash
    - Upserts position (weighted avg_cost if ticker already held)
    - Inserts trade record
    Returns updated portfolio status dict.
    Raises ValueError if insufficient cash.
    """
    total = shares * price
    conn = get_connection(db_path)
    try:
        with conn:
            cash_row = conn.execute("SELECT cash FROM account WHERE id=1").fetchone()
            cash = cash_row["cash"]
            if total > cash:
                raise ValueError(
                    f"Insufficient cash: need ${total:.2f} but only have ${cash:.2f}"
                )
            # Update cash
            conn.execute("UPDATE account SET cash = cash - ? WHERE id=1", (total,))
            # Upsert position with weighted average cost
            existing = conn.execute(
                "SELECT shares, avg_cost FROM positions WHERE ticker=?", (ticker,)
            ).fetchone()
            if existing is None:
                conn.execute(
                    "INSERT INTO positions (ticker, shares, avg_cost) VALUES (?, ?, ?)",
                    (ticker, shares, price),
                )
            else:
                old_shares = existing["shares"]
                old_avg_cost = existing["avg_cost"]
                new_shares = old_shares + shares
                new_avg_cost = (old_shares * old_avg_cost + shares * price) / new_shares
                conn.execute(
                    "UPDATE positions SET shares=?, avg_cost=? WHERE ticker=?",
                    (new_shares, new_avg_cost, ticker),
                )
            # Record trade
            conn.execute(
                "INSERT INTO trades (action, ticker, shares, price, total, reasoning) "
                "VALUES ('BUY', ?, ?, ?, ?, ?)",
                (ticker, shares, price, total, reasoning),
            )
    finally:
        conn.close()
    return get_portfolio_status(db_path)


def execute_sell(ticker: str, shares: int, price: float, reasoning: str, db_path=DB_PATH) -> dict:
    """
    Executes a paper SELL. Atomic transaction.
    - Adds shares*price to cash
    - Reduces or removes position
    - Inserts trade record
    Returns updated portfolio status dict.
    Raises ValueError if position not held or insufficient shares.
    """
    total = shares * price
    conn = get_connection(db_path)
    try:
        with conn:
            existing = conn.execute(
                "SELECT shares, avg_cost FROM positions WHERE ticker=?", (ticker,)
            ).fetchone()
            if existing is None:
                raise ValueError(f"No position held for {ticker}")
            held = existing["shares"]
            if shares > held:
                raise ValueError(
                    f"Insufficient shares of {ticker}: want to sell {shares} but only hold {held}"
                )
            # Update cash
            conn.execute("UPDATE account SET cash = cash + ? WHERE id=1", (total,))
            # Update or remove position
            remaining = held - shares
            if remaining == 0:
                conn.execute("DELETE FROM positions WHERE ticker=?", (ticker,))
            else:
                conn.execute(
                    "UPDATE positions SET shares=? WHERE ticker=?",
                    (remaining, ticker),
                )
            # Record trade
            conn.execute(
                "INSERT INTO trades (action, ticker, shares, price, total, reasoning) "
                "VALUES ('SELL', ?, ?, ?, ?, ?)",
                (ticker, shares, price, total, reasoning),
            )
    finally:
        conn.close()
    return get_portfolio_status(db_path)


def save_daily_snapshot(date: str, total_value: float, cash: float, pnl_pct: float, db_path=DB_PATH) -> None:
    """
    Upserts a daily_snapshots row. date format: YYYY-MM-DD.
    Uses INSERT OR REPLACE.
    """
    conn = get_connection(db_path)
    try:
        with conn:
            conn.execute(
                "INSERT OR REPLACE INTO daily_snapshots (date, total_value, cash, pnl_pct) "
                "VALUES (?, ?, ?, ?)",
                (date, total_value, cash, pnl_pct),
            )
    finally:
        conn.close()


def get_trade_history(limit: int = 10, db_path=DB_PATH) -> list[dict]:
    """
    Returns last `limit` trades ordered by timestamp DESC.
    Each dict: {id, timestamp, action, ticker, shares, price, total, reasoning}
    """
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT id, timestamp, action, ticker, shares, price, total, reasoning "
            "FROM trades ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {
                "id": r["id"],
                "timestamp": r["timestamp"],
                "action": r["action"],
                "ticker": r["ticker"],
                "shares": r["shares"],
                "price": r["price"],
                "total": r["total"],
                "reasoning": r["reasoning"],
            }
            for r in rows
        ]
    finally:
        conn.close()
