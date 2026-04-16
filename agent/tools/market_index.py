"""
market_index.py — Fetches NASDAQ and S&P 500 to determine today's market direction.
Safe: never raises on normal inputs.
"""

from __future__ import annotations

import yfinance as yf

_FALLBACK = {
    "nasdaq_change_pct": 0.0,
    "sp500_change_pct": 0.0,
    "direction": "neutral",
    "summary": "Data unavailable",
}


def get_market_direction() -> dict:
    """
    Returns a dict describing today's market direction.

    Keys:
        nasdaq_change_pct  – today's % change for NASDAQ (^IXIC)
        sp500_change_pct   – today's % change for S&P 500 (^GSPC)
        direction          – "risk_on", "neutral", or "risk_off"
        summary            – plain-English one-liner

    Direction logic:
        Both indexes up > 0.5%  → "risk_on"
        Either index down > 1%  → "risk_off"
        Otherwise               → "neutral"
    """
    try:
        df = yf.download(
            ["^IXIC", "^GSPC"],
            period="2d",
            interval="1d",
            progress=False,
            auto_adjust=True,
        )

        # df["Close"] has columns ["^GSPC", "^IXIC"] (alphabetical)
        close = df["Close"].dropna()
        if len(close) < 2:
            return dict(_FALLBACK)

        yesterday = close.iloc[-2]
        today = close.iloc[-1]

        nasdaq_chg = float((today["^IXIC"] / yesterday["^IXIC"] - 1) * 100)
        sp500_chg = float((today["^GSPC"] / yesterday["^GSPC"] - 1) * 100)

        if nasdaq_chg > 0.5 and sp500_chg > 0.5:
            direction = "risk_on"
        elif nasdaq_chg < -1.0 or sp500_chg < -1.0:
            direction = "risk_off"
        else:
            direction = "neutral"

        nasdaq_sign = "+" if nasdaq_chg >= 0 else ""
        sp500_sign = "+" if sp500_chg >= 0 else ""
        summary = (
            f"NASDAQ {nasdaq_sign}{nasdaq_chg:.1f}%, "
            f"S&P500 {sp500_sign}{sp500_chg:.1f}% — {direction}"
        )

        return {
            "nasdaq_change_pct": nasdaq_chg,
            "sp500_change_pct": sp500_chg,
            "direction": direction,
            "summary": summary,
        }

    except Exception:
        return dict(_FALLBACK)
