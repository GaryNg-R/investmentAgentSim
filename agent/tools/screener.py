"""
screener.py — Scans the watchlist for high-momentum stocks.
Safe: never raises on normal inputs.
"""

from __future__ import annotations

from agent.tools.stock_data import get_history, get_price
from agent.tools.technical import calculate_indicators, get_momentum_score

WATCHLIST = [
    "NVDA", "AMD", "TSLA", "META", "AMZN",
    "GOOGL", "MSFT", "AAPL", "COIN", "PLTR",
    "CRWD", "SNOW", "NET", "QQQ", "SOXL",
    "SOXS", "MSTR", "IONQ",
]


def screen_stocks(market_direction: str = "neutral") -> list[dict]:
    """
    For each ticker in WATCHLIST:
      1. Fetch history (3mo) via get_history()
      2. calculate_indicators() on the DataFrame
      3. get_momentum_score() to get score + signals
      4. Get current price via get_price()

    Sort results by score descending.

    If market_direction == "risk_off": return empty list (no new buy candidates on down days).

    Each result dict:
    {
        "ticker": str,
        "score": int,
        "price": float | None,
        "rsi": float,
        "signals": list[str]
    }

    Skip tickers where get_history() returns empty DataFrame.
    Return the full sorted list (all tickers that had data).
    """
    if market_direction == "risk_off":
        return []

    results: list[dict] = []

    for ticker in WATCHLIST:
        df = get_history(ticker, period="3mo")
        if df.empty:
            continue

        df = calculate_indicators(df)
        momentum = get_momentum_score(ticker, df)
        price = get_price(ticker)

        results.append({
            "ticker": ticker,
            "score": momentum["score"],
            "price": price,
            "rsi": momentum["rsi"],
            "signals": momentum["signals"],
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results
