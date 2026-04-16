"""
technical.py — Technical analysis indicators and momentum scoring.
Uses the `ta` library on OHLCV DataFrames.
Safe: never raises on normal inputs.
"""

from __future__ import annotations

import pandas as pd
import ta.momentum
import ta.trend


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds these columns to the DataFrame and returns it:
    - RSI: 14-period RSI (ta.momentum.RSIIndicator)
    - MACD: MACD line (ta.trend.MACD)
    - MACD_signal: signal line
    - MACD_hist: histogram (MACD - signal)
    - SMA_20: 20-period simple moving average
    - Volume_SMA_20: 20-period SMA of volume
    Returns df unchanged (with added columns) or original df on error.
    """
    try:
        close = df["Close"]
        volume = df["Volume"]

        rsi = ta.momentum.RSIIndicator(close=close, window=14)
        df["RSI"] = rsi.rsi()

        macd = ta.trend.MACD(close=close)
        df["MACD"] = macd.macd()
        df["MACD_signal"] = macd.macd_signal()
        df["MACD_hist"] = macd.macd_diff()

        df["SMA_20"] = close.rolling(window=20).mean()
        df["Volume_SMA_20"] = volume.rolling(window=20).mean()

        return df
    except Exception:
        return df


def get_momentum_score(ticker: str, df: pd.DataFrame) -> dict:
    """
    Returns dict: {ticker, score (int 0-100), rsi (float), signals (list of str)}

    Score calculation (starts at 50):
    +15 if RSI between 55 and 70
    -10 if RSI > 70 (overbought)
    -15 if RSI < 40
    +15 if MACD above signal line (last row)
    -10 if MACD below signal line (last row)
    +5  if MACD_hist is rising (last row > second-to-last row)
    +10 if close price > SMA_20 (last row)
    -10 if close price < SMA_20 (last row)
    +5  if volume > 1.5x Volume_SMA_20 (last row)

    Clamp score to [0, 100].
    signals list contains plain-English strings for each active signal.
    On any error (empty df, missing columns), return score=50, rsi=0, signals=[].
    """
    _error = {"ticker": ticker, "score": 50, "rsi": 0.0, "signals": []}

    try:
        required_cols = {"RSI", "MACD", "MACD_signal", "MACD_hist", "SMA_20", "Volume_SMA_20", "Close", "Volume"}
        if df.empty or not required_cols.issubset(df.columns):
            return _error

        if len(df) < 2:
            return _error

        last = df.iloc[-1]
        prev = df.iloc[-2]

        rsi = float(last["RSI"])
        if pd.isna(rsi):
            return _error

        score = 50
        signals: list[str] = []

        # RSI signals
        if 55 <= rsi <= 70:
            score += 15
            signals.append(f"RSI {rsi:.1f} — bullish momentum zone (55–70)")
        elif rsi > 70:
            score -= 10
            signals.append(f"RSI {rsi:.1f} — overbought (>70)")
        elif rsi < 40:
            score -= 15
            signals.append(f"RSI {rsi:.1f} — weak momentum (<40)")

        # MACD vs signal
        macd_val = last["MACD"]
        macd_sig = last["MACD_signal"]
        macd_hist = last["MACD_hist"]
        prev_hist = prev["MACD_hist"]

        if not pd.isna(macd_val) and not pd.isna(macd_sig):
            if macd_val > macd_sig:
                score += 15
                signals.append("MACD above signal line (bullish crossover)")
            elif macd_val < macd_sig:
                score -= 10
                signals.append("MACD below signal line (bearish)")

        # MACD histogram rising
        if not pd.isna(macd_hist) and not pd.isna(prev_hist):
            if macd_hist > prev_hist:
                score += 5
                signals.append("MACD histogram rising (increasing momentum)")

        # Price vs SMA_20
        close_val = last["Close"]
        sma20 = last["SMA_20"]
        if not pd.isna(close_val) and not pd.isna(sma20):
            if close_val > sma20:
                score += 10
                signals.append(f"Price ${close_val:.2f} above SMA-20 ${sma20:.2f}")
            elif close_val < sma20:
                score -= 10
                signals.append(f"Price ${close_val:.2f} below SMA-20 ${sma20:.2f}")

        # Volume surge
        volume_val = last["Volume"]
        vol_sma20 = last["Volume_SMA_20"]
        if not pd.isna(volume_val) and not pd.isna(vol_sma20) and vol_sma20 > 0:
            if volume_val > 1.5 * vol_sma20:
                score += 5
                signals.append("Volume surge (>1.5x 20-day average)")

        score = max(0, min(100, score))
        return {"ticker": ticker, "score": int(score), "rsi": rsi, "signals": signals}

    except Exception:
        return _error
