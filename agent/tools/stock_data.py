"""
stock_data.py — yfinance wrappers for per-ticker data.
All functions are safe: they never raise on normal inputs.
"""

from __future__ import annotations

import pandas as pd
import yfinance as yf


def get_price(ticker: str) -> float | None:
    """
    Returns the latest closing price for the ticker.
    Tries fast_info['lastPrice'] first, falls back to history().
    Returns None if data is unavailable.
    """
    try:
        t = yf.Ticker(ticker)
        price = t.fast_info.get("lastPrice")
        if price is not None and price > 0:
            return float(price)
        # Fallback: last close from recent history
        hist = t.history(period="5d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
        return None
    except Exception:
        return None


def get_history(ticker: str, period: str = "3mo") -> pd.DataFrame:
    """
    Returns an OHLCV DataFrame for the given period.
    Valid periods: 1d, 5d, 1mo, 3mo, 6mo, 1y
    Returns an empty DataFrame on error.
    """
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period=period)
        return hist
    except Exception:
        return pd.DataFrame()


def get_company_info(ticker: str) -> dict:
    """
    Returns a dict with keys: sector, market_cap, week_52_high, week_52_low.
    Returns an empty dict on error.
    """
    try:
        info = yf.Ticker(ticker).info
        return {
            "sector": info.get("sector"),
            "market_cap": info.get("marketCap"),
            "week_52_high": info.get("fiftyTwoWeekHigh"),
            "week_52_low": info.get("fiftyTwoWeekLow"),
        }
    except Exception:
        return {}
