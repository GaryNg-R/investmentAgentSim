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

## Knowledge & feedback loop

The agent connects to an external Obsidian knowledge base through a journal-and-memory loop:

- **Daily journal** — at the end of each `run2`, the agent writes a git-tracked file `data/journal/{date}.json` containing that day's daily lesson, market education summary, intended trade decisions, and an outcome snapshot (total value, cash, P&L, open positions). Because the journal is committed, the full history travels with a `git pull` and does not depend on the gitignored database.
- **Strategy memory** — `data/strategy_memory.md` holds accumulated, plain-language lessons. On every run the agent injects this file into Claude's prompt as a STRATEGY MEMORY section, so it weighs past lessons when deciding. The memory is guidance only and never overrides the enforced risk rules. If the file is absent, the prompt is unchanged.
- **The `trading-review` skill** — lives in the user's Obsidian vault (not in this repo). When run, it pulls this repo, captures each journal day into vault notes (glossary, market recaps, trade log), analyzes decisions against outcomes, appends distilled lessons to `data/strategy_memory.md`, and pushes — feeding the next run.
