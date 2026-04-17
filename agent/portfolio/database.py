"""SQLite database layer for the investment agent portfolio."""

import sqlite3

DB_PATH = "data/portfolio.db"

_DDL = """
CREATE TABLE IF NOT EXISTS account (
    id      INTEGER PRIMARY KEY,
    cash    REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS positions (
    ticker    TEXT PRIMARY KEY,
    shares    REAL NOT NULL,
    avg_cost  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS trades (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT DEFAULT CURRENT_TIMESTAMP,
    action      TEXT NOT NULL CHECK(action IN ('BUY','SELL')),
    ticker      TEXT NOT NULL,
    shares      REAL NOT NULL,
    price       REAL NOT NULL,
    total       REAL NOT NULL,
    reasoning   TEXT
);

CREATE TABLE IF NOT EXISTS daily_snapshots (
    date         TEXT PRIMARY KEY,
    total_value  REAL NOT NULL,
    cash         REAL NOT NULL,
    pnl_pct      REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS benchmark_account (
    id              INTEGER PRIMARY KEY,
    voo_shares      REAL NOT NULL,
    total_deposited REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS benchmark_snapshots (
    date            TEXT PRIMARY KEY,
    voo_shares      REAL NOT NULL,
    voo_price       REAL NOT NULL,
    total_value     REAL NOT NULL,
    total_deposited REAL NOT NULL
);
"""


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Return a sqlite3 connection with Row factory and WAL journal mode."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(db_path: str = DB_PATH) -> None:
    """Create tables if they do not exist, then seed the initial $10,000 cash balance."""
    conn = get_connection(db_path)
    try:
        conn.executescript(_DDL)
        row = conn.execute("SELECT cash FROM account WHERE id=1").fetchone()
        if row is None:
            conn.execute("INSERT INTO account (id, cash) VALUES (1, 10000.0)")
            conn.commit()
    finally:
        conn.close()
