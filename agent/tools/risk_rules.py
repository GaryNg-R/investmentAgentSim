"""
risk_rules.py — 4 hardcoded trading guardrails enforced before every trade.
All functions are pure logic; no external calls.
"""

from __future__ import annotations

# Risk rule constants
MAX_POSITION_PCT = 0.25    # max 25% of portfolio in one stock
STOP_LOSS_PCT = -0.07      # -7% stop-loss triggers auto-sell
PROFIT_TARGET_PCT = 0.12   # +12% profit target triggers auto-sell
MAX_POSITIONS = 3          # max 3 open positions at once


def validate_buy(ticker: str, shares: int, price: float, portfolio: dict) -> tuple[bool, str]:
    """
    Validates a buy order against risk rules.

    portfolio dict structure:
    {
        'cash': float,
        'positions': list of dicts with {'ticker', 'shares', 'avg_cost'},
        'total_value': float,
        'position_count': int
    }

    Checks (in order):
    1. shares >= 1
    2. cash >= shares * price (sufficient cash)
    3. position_count < MAX_POSITIONS OR ticker already in positions (not exceeding max)
    4. (shares * price) / total_value <= MAX_POSITION_PCT (position size limit)

    Returns (True, "ok") if all pass.
    Returns (False, reason_string) on first failure.
    """
    # Check 1: shares >= 1
    if shares < 1:
        return (False, "shares must be >= 1")

    # Check 2: sufficient cash
    cost = shares * price
    if portfolio["cash"] < cost:
        return (False, f"insufficient cash: need ${cost:.2f} but have ${portfolio['cash']:.2f}")

    # Check 3: not exceeding max positions (unless ticker already held)
    ticker_held = any(pos["ticker"] == ticker for pos in portfolio["positions"])
    if portfolio["position_count"] >= MAX_POSITIONS and not ticker_held:
        return (False, f"max positions ({MAX_POSITIONS}) reached; cannot add new ticker")

    # Check 4: position size limit
    position_pct = cost / portfolio["total_value"]
    if position_pct > MAX_POSITION_PCT:
        return (
            False,
            f"position size ${cost:.2f} exceeds {MAX_POSITION_PCT*100:.0f}% of portfolio (${portfolio['total_value']*MAX_POSITION_PCT:.2f})"
        )

    return (True, "ok")


def validate_sell(ticker: str, shares: int, portfolio: dict) -> tuple[bool, str]:
    """
    Validates a sell order against risk rules.

    Checks:
    1. ticker is in portfolio positions
    2. shares <= held shares for that ticker
    3. shares >= 1

    Returns (True, "ok") or (False, reason_string).
    """
    # Check 1: ticker is held
    position = next((pos for pos in portfolio["positions"] if pos["ticker"] == ticker), None)
    if position is None:
        return (False, f"ticker {ticker} not in portfolio")

    # Check 2: shares >= 1
    if shares < 1:
        return (False, "shares must be >= 1")

    # Check 3: shares <= held shares
    if shares > position["shares"]:
        return (
            False,
            f"insufficient shares of {ticker}: want to sell {shares} but only hold {position['shares']}"
        )

    return (True, "ok")


def check_stop_loss(ticker: str, current_price: float, avg_cost: float) -> bool:
    """
    Returns True if current_price has dropped <= STOP_LOSS_PCT (-7%) from avg_cost.

    Calculation: (current_price / avg_cost - 1) <= STOP_LOSS_PCT
    """
    if avg_cost <= 0:
        return False

    return_pct = (current_price / avg_cost) - 1.0
    return return_pct <= STOP_LOSS_PCT


def check_profit_target(ticker: str, current_price: float, avg_cost: float) -> bool:
    """
    Returns True if current_price has risen >= PROFIT_TARGET_PCT (+12%) from avg_cost.

    Calculation: (current_price / avg_cost - 1) >= PROFIT_TARGET_PCT
    """
    if avg_cost <= 0:
        return False

    return_pct = (current_price / avg_cost) - 1.0
    return return_pct >= PROFIT_TARGET_PCT
