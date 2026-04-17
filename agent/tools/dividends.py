"""
dividends.py — DRIP dividend reinvestment for agent positions and VOO benchmark.
On each ex-dividend date, dividends are reinvested as fractional shares.
Never raises — returns [] on any error so run2 is never blocked.
"""

from __future__ import annotations

from datetime import date

from agent.portfolio.database import DB_PATH, get_connection, init_db


def process_dividends(db_path: str = DB_PATH, _today: date | None = None) -> list[dict]:
    """
    Check each held position and the VOO benchmark for ex-dividend events today.
    Reinvest as fractional shares. Idempotent via UNIQUE(date, ticker, account).
    Returns list of event dicts (one per reinvestment), or [] if nothing happened.
    """
    try:
        today = _today or date.today()
        today_str = today.isoformat()

        init_db(db_path)
        events: list[dict] = []

        conn = get_connection(db_path)
        try:
            # --- Agent positions ---
            pos_rows = conn.execute(
                "SELECT ticker, shares FROM positions"
            ).fetchall()

            for pos in pos_rows:
                ticker = pos["ticker"]
                shares_held = pos["shares"]

                already = conn.execute(
                    "SELECT 1 FROM dividend_events WHERE date=? AND ticker=? AND account='agent'",
                    (today_str, ticker),
                ).fetchone()
                if already:
                    continue

                div_per_share = _get_dividend_today(ticker, today)
                if div_per_share is None or div_per_share == 0.0:
                    continue

                current_price = _get_current_price(ticker)
                if not current_price:
                    continue

                dividend_cash = div_per_share * shares_held
                shares_added = dividend_cash / current_price

                conn.execute(
                    "UPDATE positions SET shares = shares + ? WHERE ticker = ?",
                    (shares_added, ticker),
                )
                conn.execute(
                    "INSERT INTO dividend_events (date, ticker, account, shares_held, div_per_share, shares_added) "
                    "VALUES (?, ?, 'agent', ?, ?, ?)",
                    (today_str, ticker, shares_held, div_per_share, shares_added),
                )
                conn.commit()

                events.append({
                    "ticker": ticker,
                    "account": "agent",
                    "shares_held": shares_held,
                    "div_per_share": div_per_share,
                    "shares_added": shares_added,
                    "total_dividend": dividend_cash,
                })

            # --- VOO benchmark ---
            bench_row = conn.execute(
                "SELECT voo_shares FROM benchmark_account WHERE id=1"
            ).fetchone()

            if bench_row:
                voo_shares = bench_row["voo_shares"]

                already = conn.execute(
                    "SELECT 1 FROM dividend_events WHERE date=? AND ticker='VOO' AND account='benchmark'",
                    (today_str,),
                ).fetchone()

                if not already:
                    div_per_share = _get_dividend_today("VOO", today)
                    if div_per_share is not None and div_per_share != 0.0:
                        current_price = _get_current_price("VOO")
                        if current_price:
                            dividend_cash = div_per_share * voo_shares
                            shares_added = dividend_cash / current_price

                            conn.execute(
                                "UPDATE benchmark_account SET voo_shares = voo_shares + ? WHERE id=1",
                                (shares_added,),
                            )
                            conn.execute(
                                "INSERT INTO dividend_events (date, ticker, account, shares_held, div_per_share, shares_added) "
                                "VALUES (?, 'VOO', 'benchmark', ?, ?, ?)",
                                (today_str, voo_shares, div_per_share, shares_added),
                            )
                            conn.commit()

                            events.append({
                                "ticker": "VOO",
                                "account": "benchmark",
                                "shares_held": voo_shares,
                                "div_per_share": div_per_share,
                                "shares_added": shares_added,
                                "total_dividend": dividend_cash,
                            })

        finally:
            conn.close()

        return events

    except Exception as exc:
        print(f"[dividends] process_dividends error: {exc}")
        return []


def _get_dividend_today(ticker: str, today: date) -> float | None:
    """Return dividend per share if today is ex-dividend date for ticker, else None."""
    try:
        import yfinance as yf
        divs = yf.Ticker(ticker).dividends
        if divs is None or divs.empty:
            return None
        for dt, amount in divs.items():
            if hasattr(dt, "date"):
                dt = dt.date()
            if dt == today:
                return float(amount)
        return None
    except Exception:
        return None


def _get_current_price(ticker: str) -> float | None:
    """Fetch current price for ticker. Returns None on failure."""
    try:
        from agent.tools.stock_data import get_price
        return get_price(ticker)
    except Exception:
        return None
