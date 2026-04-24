# Investment Agent Sim

An AI-powered paper trading bot that runs entirely on real market data — no real money at stake.

## What it does

Every weekday it runs hourly from 6am to 2pm. Each run scans Yahoo Finance for the day's top movers and most active stocks, scores them using technical indicators (RSI, MACD, moving averages, volume), then feeds the ranked candidates alongside the current portfolio and recent news headlines to Claude. Claude reasons about which stocks to buy or sell and returns structured decisions with a conviction level — high, medium, or low — which directly determines position size (20%, 12%, or 7% of portfolio). Throughout the day it monitors every open position and auto-exits at -7% (stop-loss) or +12% (profit target).

Trades only execute during NYSE market hours (9:30am–4pm ET), so early morning runs plan ahead and later runs catch up on intraday moves.

## The question it's answering

Can an AI agent picking individual stocks outperform simply buying and holding VOO (S&P 500 ETF)? Results are tracked and compared against VOO at 1, 3, and 6-month intervals.

## Commands

```
python -m agent.main run1      # Scan market + ask Claude for a trade plan
python -m agent.main run2      # Execute the trade plan
python -m agent.main monitor   # Check stop-loss/profit targets on open positions
python -m agent.main history   # Print trade history and portfolio summary
python -m agent.main weekly    # Send weekly performance digest to Telegram
```
