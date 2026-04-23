"""Reusable test DB seed for dashboard_export tests."""

import sqlite3

from agent.portfolio.database import init_db


def seed_known_database(db_path: str) -> None:
    """Seed a fresh DB with a known, deterministic state for testing."""
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    try:
        # Account
        conn.execute("UPDATE account SET cash = 5238.89 WHERE id = 1")

        # Positions
        conn.execute("DELETE FROM positions")
        conn.executemany(
            "INSERT INTO positions (ticker, shares, avg_cost) VALUES (?, ?, ?)",
            [
                ("META", 3.0, 674.16),
                ("COIN", 12.0, 195.90),
                ("TSLA", 2.0, 398.86),
            ],
        )

        # Trades — 7 rows matching the scenario described in the plan
        conn.execute("DELETE FROM trades")
        conn.executemany(
            "INSERT INTO trades (id, timestamp, action, ticker, shares, price, total, reasoning) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (1, "2026-04-16 15:47:47", "BUY",  "TSLA", 6.0, 388.37,  2330.22, "initial buy"),
                (2, "2026-04-16 15:47:48", "BUY",  "META", 3.0, 674.16,  2022.48, "meta buy"),
                (3, "2026-04-16 18:27:20", "BUY",  "COIN", 12.0, 195.90, 2350.80, "coin buy"),
                (4, "2026-04-16 18:28:25", "SELL", "TSLA", 6.0, 385.375, 2312.25, "sell tsla"),
                (5, "2026-04-16 18:28:26", "BUY",  "MSTR", 17.0, 143.69, 2442.73, "mstr buy"),
                (6, "2026-04-17 14:34:54", "SELL", "MSTR", 17.0, 168.86, 2870.62, "mstr sell profit"),
                (7, "2026-04-17 14:34:55", "BUY",  "TSLA", 2.0, 398.86,  797.72,  "tsla re-buy"),
            ],
        )

        # Daily snapshots — 5 rows, ascending dates, one peak-then-dip for drawdown test
        conn.execute("DELETE FROM daily_snapshots")
        conn.executemany(
            "INSERT INTO daily_snapshots (date, total_value, cash, pnl_pct) VALUES (?, ?, ?, ?)",
            [
                ("2026-04-16", 10050.00, 5200.00, 0.50),
                ("2026-04-17", 10200.00, 5238.89, 2.00),
                ("2026-04-18", 10180.00, 5238.89, 1.80),
                ("2026-04-21", 10250.00, 5238.89, 2.50),
                ("2026-04-22", 10409.92, 5238.89, 4.10),
            ],
        )

        # Benchmark account
        conn.execute("DELETE FROM benchmark_account")
        conn.execute(
            "INSERT INTO benchmark_account (id, voo_shares, total_deposited) VALUES (1, 15.507, 10000.0)"
        )

        # Benchmark snapshots
        conn.execute("DELETE FROM benchmark_snapshots")
        conn.executemany(
            "INSERT INTO benchmark_snapshots (date, voo_shares, voo_price, total_value, total_deposited) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                ("2026-04-16", 15.507, 645.00, 9951.02, 10000.0),
                ("2026-04-21", 15.507, 648.50, 10055.29, 10000.0),
                ("2026-04-22", 15.507, 651.00, 10095.06, 10000.0),
            ],
        )

        conn.commit()
    finally:
        conn.close()
