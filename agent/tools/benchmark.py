"""benchmark.py — VOO buy-and-hold benchmark tracker.
Tracks a parallel $10,000 account that buys VOO immediately and adds $100 every Monday.
Never raises — returns {} on any error so run2 is never blocked.
"""

from __future__ import annotations

from datetime import date

from agent.portfolio.database import DB_PATH, get_connection, init_db

INITIAL_DEPOSIT = 10_000.0
WEEKLY_DEPOSIT = 100.0


def update_benchmark(db_path: str = DB_PATH, _today: date | None = None) -> dict:  # FEAT-002
    """
    Called every run2. Handles first-run seeding, Monday deposits, and daily snapshots.
    _today is injectable for testing; defaults to date.today().
    Returns status dict or {} on any error.
    """
    try:
        today = _today or date.today()
        today_str = today.isoformat()

        init_db(db_path)
        voo_price = _get_voo_price()
        if not voo_price or voo_price <= 0:
            return {}

        conn = get_connection(db_path)
        try:
            deposit_made = False
            row = conn.execute(
                "SELECT voo_shares, total_deposited FROM benchmark_account WHERE id=1"
            ).fetchone()

            if row is None:
                voo_shares = INITIAL_DEPOSIT / voo_price
                total_deposited = INITIAL_DEPOSIT
                conn.execute(
                    "INSERT INTO benchmark_account (id, voo_shares, total_deposited) VALUES (1, ?, ?)",
                    (voo_shares, total_deposited),
                )
                conn.commit()
            else:
                voo_shares = row["voo_shares"]
                total_deposited = row["total_deposited"]

                is_monday = today.weekday() == 0
                already_snapped = conn.execute(
                    "SELECT 1 FROM benchmark_snapshots WHERE date=?", (today_str,)
                ).fetchone()

                if is_monday and not already_snapped:
                    new_shares = WEEKLY_DEPOSIT / voo_price
                    voo_shares += new_shares
                    total_deposited += WEEKLY_DEPOSIT
                    conn.execute(
                        "UPDATE benchmark_account SET voo_shares=?, total_deposited=? WHERE id=1",
                        (voo_shares, total_deposited),
                    )
                    conn.commit()
                    deposit_made = True

            total_value = voo_shares * voo_price
            conn.execute(
                """INSERT INTO benchmark_snapshots
                       (date, voo_shares, voo_price, total_value, total_deposited)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(date) DO UPDATE SET
                       voo_shares=excluded.voo_shares,
                       voo_price=excluded.voo_price,
                       total_value=excluded.total_value,
                       total_deposited=excluded.total_deposited""",
                (today_str, voo_shares, voo_price, total_value, total_deposited),
            )
            conn.commit()

            return {
                "voo_shares": voo_shares,
                "voo_price": voo_price,
                "total_value": total_value,
                "total_deposited": total_deposited,
                "deposit_made": deposit_made,
            }
        finally:
            conn.close()

    except Exception as exc:
        print(f"[benchmark] update_benchmark error: {exc}")
        return {}


def _get_voo_price() -> float | None:
    """Fetch current VOO price via yfinance. Returns None on any failure."""
    try:
        import yfinance as yf
        price = yf.Ticker("VOO").fast_info["last_price"]
        if price and float(price) > 0:
            return float(price)
        return None
    except Exception:
        return None
