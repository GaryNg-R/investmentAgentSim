"""
Tests for agent/tools/technical.py — uses synthetic data, no yfinance calls.
"""

import numpy as np
import pandas as pd
import pytest

from agent.tools.technical import calculate_indicators, get_momentum_score


def _make_df(rows: int = 30) -> pd.DataFrame:
    """Build a synthetic OHLCV DataFrame with `rows` entries."""
    np.random.seed(42)
    close = 100 + np.cumsum(np.random.randn(rows) * 0.5)
    high = close + np.abs(np.random.randn(rows) * 0.3)
    low = close - np.abs(np.random.randn(rows) * 0.3)
    open_ = close + np.random.randn(rows) * 0.2
    volume = np.random.randint(1_000_000, 5_000_000, size=rows).astype(float)

    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume}
    )


class TestCalculateIndicators:
    def test_calculate_indicators_adds_columns(self):
        # MACD default uses 26-period EMA + 9-period signal → needs ≥34 rows for any non-NaN
        df = _make_df(60)
        result = calculate_indicators(df)

        expected_cols = {"RSI", "MACD", "MACD_signal", "MACD_hist", "SMA_20", "Volume_SMA_20"}
        for col in expected_cols:
            assert col in result.columns, f"Missing column: {col}"

        # Columns should not be entirely NaN (enough data was provided)
        for col in expected_cols:
            assert not result[col].isna().all(), f"Column {col} is all NaN"

    def test_calculate_indicators_returns_dataframe(self):
        df = _make_df(30)
        result = calculate_indicators(df)
        assert isinstance(result, pd.DataFrame)

    def test_calculate_indicators_preserves_original_columns(self):
        df = _make_df(30)
        original_cols = set(df.columns)
        result = calculate_indicators(df)
        assert original_cols.issubset(result.columns)


class TestMomentumScore:
    def test_momentum_score_range(self):
        """Score is always between 0 and 100."""
        df = _make_df(30)
        df = calculate_indicators(df)
        result = get_momentum_score("TEST", df)

        assert 0 <= result["score"] <= 100
        assert result["ticker"] == "TEST"
        assert isinstance(result["rsi"], float)
        assert isinstance(result["signals"], list)

    def test_momentum_score_empty_df(self):
        """Empty DataFrame returns score=50, rsi=0, signals=[]."""
        result = get_momentum_score("TEST", pd.DataFrame())

        assert result["score"] == 50
        assert result["rsi"] == 0.0
        assert result["signals"] == []
        assert result["ticker"] == "TEST"

    def test_momentum_score_missing_columns(self):
        """DataFrame missing indicator columns returns default."""
        df = _make_df(30)  # no indicators calculated
        result = get_momentum_score("TEST", df)

        assert result["score"] == 50
        assert result["rsi"] == 0.0
        assert result["signals"] == []

    def test_momentum_score_returns_dict_keys(self):
        df = _make_df(30)
        df = calculate_indicators(df)
        result = get_momentum_score("AAPL", df)

        assert set(result.keys()) == {"ticker", "score", "rsi", "signals"}

    def test_momentum_score_signals_are_strings(self):
        df = _make_df(30)
        df = calculate_indicators(df)
        result = get_momentum_score("NVDA", df)

        for signal in result["signals"]:
            assert isinstance(signal, str)

    def test_momentum_score_clamp_high(self):
        """Artificially trigger all positive signals; score must not exceed 100."""
        df = _make_df(50)
        df = calculate_indicators(df)

        # Force RSI into bullish zone, MACD above signal, price above SMA, volume surge
        df["RSI"] = 60.0
        df["MACD"] = 1.0
        df["MACD_signal"] = 0.5
        df["MACD_hist"] = df["MACD"] - df["MACD_signal"]
        # Make histogram rise on last row
        df.iloc[-1, df.columns.get_loc("MACD_hist")] = 1.0
        df.iloc[-2, df.columns.get_loc("MACD_hist")] = 0.5
        # Price above SMA
        df["SMA_20"] = df["Close"] * 0.9
        # Volume surge
        df["Volume_SMA_20"] = df["Volume"] * 0.5

        result = get_momentum_score("TEST", df)
        assert result["score"] <= 100

    def test_momentum_score_clamp_low(self):
        """Artificially trigger all negative signals; score must not go below 0."""
        df = _make_df(50)
        df = calculate_indicators(df)

        df["RSI"] = 30.0  # < 40 → -15
        df["MACD"] = -1.0
        df["MACD_signal"] = 0.5  # MACD < signal → -10
        df["MACD_hist"] = df["MACD"] - df["MACD_signal"]
        # Histogram falling
        df.iloc[-1, df.columns.get_loc("MACD_hist")] = -1.0
        df.iloc[-2, df.columns.get_loc("MACD_hist")] = -0.5
        # Price below SMA
        df["SMA_20"] = df["Close"] * 1.1  # SMA above price → -10
        # Normal volume (no surge bonus)
        df["Volume_SMA_20"] = df["Volume"] * 1.0

        result = get_momentum_score("TEST", df)
        assert result["score"] >= 0
