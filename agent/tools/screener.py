"""
screener.py — Scans dynamic Yahoo Finance movers for high-momentum stocks.
Safe: never raises on normal inputs.
"""

from __future__ import annotations

from agent.tools.stock_data import get_history, get_price
from agent.tools.technical import calculate_indicators, get_momentum_score

# Core tickers always included regardless of market conditions
CORE_WATCHLIST = [
    "NVDA", "AMD", "TSLA", "META", "AMZN",
    "GOOGL", "MSFT", "AAPL", "COIN", "PLTR",
    "CRWD", "SNOW", "NET", "QQQ", "SOXL",
    "SOXS", "MSTR", "IONQ",
]

# Max candidates to score (caps API calls and compute time)
MAX_CANDIDATES = 40

# Min price filter — ignore penny stocks
MIN_PRICE = 5.0


def _fetch_dynamic_tickers() -> list[str]:
    """
    Fetches top movers from Yahoo Finance (day_gainers + most_actives).
    Returns deduplicated list of US equity tickers, price > MIN_PRICE.
    Falls back to empty list on any error.
    """
    try:
        import yfinance as yf

        tickers: list[str] = []
        for screen_name in ("day_gainers", "most_actives"):
            try:
                result = yf.screen(screen_name, count=25)
                for q in result.get("quotes", []):
                    if (
                        q.get("quoteType") == "EQUITY"
                        and q.get("region") == "US"
                        and (q.get("regularMarketPrice") or 0) >= MIN_PRICE
                    ):
                        symbol = q.get("symbol", "")
                        if symbol and symbol not in tickers:
                            tickers.append(symbol)
            except Exception:
                continue

        return tickers
    except Exception:
        return []


def screen_stocks(market_direction: str = "neutral") -> list[dict]:
    """
    Builds a candidate pool from Yahoo Finance day_gainers + most_actives,
    merged with CORE_WATCHLIST. Scores each with technical indicators.

    If market_direction == "risk_off": return empty list.

    Each result dict:
    {
        "ticker": str,
        "score": int,
        "price": float | None,
        "rsi": float,
        "signals": list[str]
    }

    Skips tickers where get_history() returns empty DataFrame.
    Returns list sorted by score descending, capped at MAX_CANDIDATES entries.
    """
    if market_direction == "risk_off":
        return []

    # Build candidate pool: dynamic movers + core list, deduplicated
    dynamic = _fetch_dynamic_tickers()
    seen: set[str] = set()
    candidates: list[str] = []
    for t in dynamic + CORE_WATCHLIST:
        if t not in seen:
            seen.add(t)
            candidates.append(t)
        if len(candidates) >= MAX_CANDIDATES:
            break

    results: list[dict] = []

    for ticker in candidates:
        df = get_history(ticker, period="60d", interval="1h")
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
