"""
news.py — Fetch recent news headlines for tickers via yfinance.
Free, no API key required.
Never raises — returns empty dict on failure.
"""

from __future__ import annotations


def get_news_headlines(tickers: list[str], max_per_ticker: int = 2) -> dict[str, list[str]]:
    """
    Fetch up to max_per_ticker recent headlines for each ticker.
    Returns dict: { "NVDA": ["headline1", "headline2"], ... }
    Skips tickers with no news silently.
    """
    try:
        import yfinance as yf
    except ImportError:
        return {}

    result: dict[str, list[str]] = {}

    for ticker in tickers:
        try:
            news = yf.Ticker(ticker).news or []
            headlines = []
            for item in news[:max_per_ticker]:
                title = item.get("title", "").strip()
                if title:
                    headlines.append(title)
            if headlines:
                result[ticker] = headlines
        except Exception:
            continue

    return result
