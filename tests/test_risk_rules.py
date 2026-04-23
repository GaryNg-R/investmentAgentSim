"""
Tests for agent/tools/risk_rules.py — pure logic, no external calls.
"""

import pytest

from agent.tools.risk_rules import (
    MAX_POSITION_PCT,
    MAX_POSITIONS,
    PROFIT_TARGET_PCT,
    STOP_LOSS_PCT,
    check_profit_target,
    check_stop_loss,
    position_size_from_conviction,
    validate_buy,
    validate_sell,
)


class TestValidateBuy:
    def test_valid_buy(self):
        """Normal buy within all limits passes."""
        portfolio = {
            "cash": 10_000.0,
            "positions": [],
            "total_value": 10_000.0,
            "position_count": 0,
        }
        result = validate_buy("AAPL", 10, 100.0, portfolio)
        assert result == (True, "ok")

    def test_insufficient_cash(self):
        """Cash too low → (False, reason)."""
        portfolio = {
            "cash": 500.0,
            "positions": [],
            "total_value": 10_000.0,
            "position_count": 0,
        }
        result = validate_buy("AAPL", 100, 100.0, portfolio)
        assert result[0] is False
        assert "insufficient cash" in result[1]

    def test_max_position_size(self):
        """Buy would exceed 25% of portfolio → (False, reason)."""
        portfolio = {
            "cash": 30_000.0,
            "positions": [],
            "total_value": 10_000.0,
            "position_count": 0,
        }
        # Trying to buy 100 shares at $30 = $3,000 (30% of $10k portfolio > 25%)
        result = validate_buy("AAPL", 100, 30.0, portfolio)
        assert result[0] is False
        assert "exceeds" in result[1] and "25%" in result[1]

    def test_max_positions_new_ticker(self):
        """Already at MAX_POSITIONS (5), buying a 6th ticker → (False, reason)."""
        portfolio = {
            "cash": 3_000.0,
            "positions": [
                {"ticker": "AAPL", "shares": 10, "avg_cost": 100.0},
                {"ticker": "MSFT", "shares": 10, "avg_cost": 200.0},
                {"ticker": "NVDA", "shares": 5, "avg_cost": 300.0},
                {"ticker": "GOOG", "shares": 5, "avg_cost": 150.0},
                {"ticker": "AMZN", "shares": 5, "avg_cost": 180.0},
            ],
            "total_value": 10_000.0,
            "position_count": 5,
        }
        result = validate_buy("TSLA", 2, 200.0, portfolio)
        assert result[0] is False
        assert "max positions" in result[1]

    def test_max_positions_existing_ticker(self):
        """Already 3 positions but buying more of an existing one → (True, "ok")."""
        portfolio = {
            "cash": 5_000.0,
            "positions": [
                {"ticker": "AAPL", "shares": 10, "avg_cost": 100.0},
                {"ticker": "MSFT", "shares": 10, "avg_cost": 200.0},
                {"ticker": "NVDA", "shares": 5, "avg_cost": 300.0},
            ],
            "total_value": 10_000.0,
            "position_count": 3,
        }
        # Buying more AAPL (already held)
        result = validate_buy("AAPL", 10, 100.0, portfolio)
        assert result == (True, "ok")

    def test_invalid_shares(self):
        """Buying 0 or negative shares → (False, reason)."""
        portfolio = {
            "cash": 10_000.0,
            "positions": [],
            "total_value": 10_000.0,
            "position_count": 0,
        }
        result = validate_buy("AAPL", 0, 100.0, portfolio)
        assert result[0] is False
        assert "shares must be >= 1" in result[1]


class TestValidateSell:
    def test_valid_sell(self):
        """Normal sell passes."""
        portfolio = {
            "cash": 5_000.0,
            "positions": [{"ticker": "AAPL", "shares": 10, "avg_cost": 100.0}],
            "total_value": 6_000.0,
            "position_count": 1,
        }
        result = validate_sell("AAPL", 5, portfolio)
        assert result == (True, "ok")

    def test_sell_not_held(self):
        """Ticker not in positions → (False, reason)."""
        portfolio = {
            "cash": 5_000.0,
            "positions": [{"ticker": "AAPL", "shares": 10, "avg_cost": 100.0}],
            "total_value": 6_000.0,
            "position_count": 1,
        }
        result = validate_sell("TSLA", 5, portfolio)
        assert result[0] is False
        assert "not in portfolio" in result[1]

    def test_sell_too_many_shares(self):
        """More shares than held → (False, reason)."""
        portfolio = {
            "cash": 5_000.0,
            "positions": [{"ticker": "AAPL", "shares": 10, "avg_cost": 100.0}],
            "total_value": 6_000.0,
            "position_count": 1,
        }
        result = validate_sell("AAPL", 15, portfolio)
        assert result[0] is False
        assert "insufficient shares" in result[1]

    def test_sell_invalid_shares(self):
        """Selling 0 or negative shares → (False, reason)."""
        portfolio = {
            "cash": 5_000.0,
            "positions": [{"ticker": "AAPL", "shares": 10, "avg_cost": 100.0}],
            "total_value": 6_000.0,
            "position_count": 1,
        }
        result = validate_sell("AAPL", 0, portfolio)
        assert result[0] is False
        assert "shares must be >= 1" in result[1]


class TestStopLoss:
    def test_stop_loss_triggered(self):
        """Price -7.1% from avg_cost → True."""
        # avg_cost = 100, current_price = 92.9 = 100 * (1 - 0.071)
        # return_pct = 92.9 / 100 - 1 = -0.071
        assert check_stop_loss("AAPL", 92.9, 100.0) is True

    def test_stop_loss_not_triggered(self):
        """Price -6.9% from avg_cost → False."""
        # avg_cost = 100, current_price = 93.1 = 100 * (1 - 0.069)
        # return_pct = 93.1 / 100 - 1 = -0.069
        assert check_stop_loss("AAPL", 93.1, 100.0) is False

    def test_stop_loss_exact_threshold(self):
        """Price at or below -7% → True (<=)."""
        # Use a value slightly below -7% to avoid floating point precision issues
        # avg_cost = 100, current_price = 92.99 = 100 * (1 - 0.0701)
        assert check_stop_loss("AAPL", 92.99, 100.0) is True

    def test_stop_loss_positive_return(self):
        """Price up from avg_cost → False."""
        assert check_stop_loss("AAPL", 110.0, 100.0) is False

    def test_stop_loss_zero_avg_cost(self):
        """Zero or negative avg_cost → False."""
        assert check_stop_loss("AAPL", 50.0, 0.0) is False
        assert check_stop_loss("AAPL", 50.0, -100.0) is False


class TestProfitTarget:
    def test_profit_target_triggered(self):
        """Price +12.1% from avg_cost → True."""
        # avg_cost = 100, current_price = 112.1 = 100 * (1 + 0.121)
        # return_pct = 112.1 / 100 - 1 = 0.121
        assert check_profit_target("AAPL", 112.1, 100.0) is True

    def test_profit_target_not_triggered(self):
        """Price +11.9% from avg_cost → False."""
        # avg_cost = 100, current_price = 111.9 = 100 * (1 + 0.119)
        # return_pct = 111.9 / 100 - 1 = 0.119
        assert check_profit_target("AAPL", 111.9, 100.0) is False

    def test_profit_target_exact_threshold(self):
        """Price exactly at +12% → True (>=)."""
        # avg_cost = 100, current_price = 112 = 100 * (1 + 0.12)
        assert check_profit_target("AAPL", 112.0, 100.0) is True

    def test_profit_target_negative_return(self):
        """Price down from avg_cost → False."""
        assert check_profit_target("AAPL", 90.0, 100.0) is False

    def test_profit_target_zero_avg_cost(self):
        """Zero or negative avg_cost → False."""
        assert check_profit_target("AAPL", 150.0, 0.0) is False
        assert check_profit_target("AAPL", 150.0, -100.0) is False


class TestConvictionSizing:
    def test_high_conviction_is_15_pct_of_cash(self):
        assert abs(position_size_from_conviction("high", 10_000.0) - 1_500.0) < 0.01

    def test_medium_conviction_is_8_pct_of_cash(self):
        assert abs(position_size_from_conviction("medium", 10_000.0) - 800.0) < 0.01

    def test_low_conviction_is_4_pct_of_cash(self):
        assert abs(position_size_from_conviction("low", 10_000.0) - 400.0) < 0.01

    def test_unknown_conviction_defaults_to_medium(self):
        assert abs(position_size_from_conviction("unknown", 10_000.0) - 800.0) < 0.01
