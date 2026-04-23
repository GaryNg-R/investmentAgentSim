"""
claude_agent.py — Builds a structured prompt, calls the Claude CLI, parses decisions,
and saves the result to data/run1_plan.json.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone

from agent.tools.news import get_news_headlines

DATA_DIR = "data"


def build_prompt(market_direction: dict, portfolio: dict, screened_stocks: list[dict]) -> str:
    """Build the structured text prompt to send to Claude."""
    today = datetime.now().strftime("%Y-%m-%d")

    # Section 1 — Goal and context
    section1 = f"""\
You are an AI investment agent managing a paper trading portfolio.
Goal: achieve 15% return (reach $11,500) from $10,000 starting capital within 30 trading days.
Today's date: {today}"""

    # Section 2 — Market direction block
    direction = market_direction.get("direction", "neutral")
    nasdaq_chg = market_direction.get("nasdaq_change_pct", 0.0)
    sp500_chg = market_direction.get("sp500_change_pct", 0.0)
    summary = market_direction.get("summary", "")

    section2 = f"""\
MARKET CONDITIONS:
Direction: {direction}
NASDAQ: {nasdaq_chg:+.1f}%
S&P 500: {sp500_chg:+.1f}%
Summary: {summary}"""

    # Section 3 — Portfolio block
    cash = portfolio.get("cash", 0.0)
    total_value = portfolio.get("total_value", 0.0)
    pnl_dollar = portfolio.get("pnl_dollar", 0.0)
    pnl_pct = portfolio.get("pnl_pct", 0.0)
    position_count = portfolio.get("position_count", 0)
    positions = portfolio.get("positions", [])

    if positions:
        positions_lines = "\n".join(
            f"  {p['ticker']}: {p['shares']} shares @ avg ${p['avg_cost']:.2f}"
            for p in positions
        )
    else:
        positions_lines = "  None"

    section3 = f"""\
CURRENT PORTFOLIO:
Cash: ${cash:.2f}
Total value: ${total_value:.2f}
P&L: ${pnl_dollar:+.2f} ({pnl_pct:+.1f}%)
Open positions ({position_count}):
{positions_lines}"""

    # Section 4 — Screened stocks
    if screened_stocks:
        header = "Ticker | Score | Price  | RSI  | Signals"
        rows = []
        for s in screened_stocks:
            ticker = s.get("ticker", "")
            score = s.get("score", 0)
            price = s.get("price", 0.0)
            rsi = s.get("rsi", 0.0)
            signals = s.get("signals", "")
            rows.append(f"{ticker:<6} | {score:<5} | ${price:<6.2f}| {rsi:<4.1f} | {signals}")
        candidates_body = header + "\n" + "\n".join(rows)
    else:
        candidates_body = "Market is risk_off — no candidates today."

    section4 = f"""\
TOP STOCK CANDIDATES (sorted by momentum score):
{candidates_body}"""

    # Section 5 — Risk rules
    open_slots = max(0, 10 - position_count)
    section5 = f"""\
RISK RULES (enforced in code — your trades must respect these):
- Max 10 open positions at once (currently {position_count} held, {open_slots} slot(s) open)
- Max 25% of portfolio in any single position
- Stop-loss: auto-sell at -7% from avg cost
- Profit target: auto-sell at +12% from avg cost
- Only trade tickers from the screened list above
- If open slots > 0 and cash > $500, strongly prefer filling them with your best candidates rather than holding idle cash"""

    # Section 5b — News headlines for top candidates
    top_tickers = [s["ticker"] for s in screened_stocks[:5]]
    news = get_news_headlines(top_tickers)
    if news:
        news_lines = []
        for ticker, headlines in news.items():
            for headline in headlines:
                news_lines.append(f"  {ticker}: {headline}")
        section5b = "RECENT NEWS (top candidates):\n" + "\n".join(news_lines)
    else:
        section5b = ""

    # Section 6 — Output instructions  # FEAT-001: added market_education and daily_lesson; FEAT-003: conviction field
    section6 = """\
REQUIRED OUTPUT FORMAT:
Respond with ONLY a JSON block inside <decisions> tags. No explanation before or after.

<decisions>
{
  "trades": [
    {"action": "BUY", "ticker": "TICKER", "conviction": "high or medium or low", "reasoning": "one sentence"},
    {"action": "SELL", "ticker": "TICKER", "shares": N, "reasoning": "one sentence"}
  ],
  "skip_new_buys": false,
  "briefing": "2-3 sentence market summary and what you decided",
  "market_education": {
    "summary_en": "3-sentence explanation of WHY the market moved today, citing specific headlines inline e.g. '...following Fed rate comments [Reuters]...'",
    "summary_zh": "Same content written in natural financial Traditional Chinese (繁體中文), as a HK/TW finance article would read — not a literal translation",
    "sources": [{"headline": "exact headline text", "publisher": "publisher name"}]
  },
  "daily_lesson": {
    "term": "The single most relevant finance concept from today — pick from what actually happened (e.g. if skip_new_buys is true pick 'Risk-Off', if NASDAQ dropped sharply pick 'Market Correction', if a stop-loss would fire pick 'Stop-Loss')",
    "explanation_en": "2-3 sentence plain English explanation a beginner can understand",
    "explanation_zh": "Same explanation in natural financial Traditional Chinese (繁體中文)"
  }
}
</decisions>

Rules:
- trades can be empty [] if no action is warranted
- BUY trades: include "conviction" (high/medium/low), do NOT include "shares" — the agent sizes the position
- SELL trades: include "shares" to sell (integer), do NOT include "conviction"
- skip_new_buys: set true if you think market conditions are too risky for new positions
- briefing: plain English summary, no jargon
- Only recommend tickers from the screened list
- Sell decisions: ticker must be in current portfolio
- market_education.sources: only cite headlines from the RECENT NEWS section above
- daily_lesson.term: must be derived from what actually happened today, not a random concept"""

    parts = [p for p in [section1, section2, section3, section4, section5, section5b, section6] if p]
    return "\n\n".join(parts)


def parse_decisions(raw_output: str) -> dict:
    """
    Extract <decisions>...</decisions> block from raw_output, parse JSON inside.
    Returns dict with keys: trades (list), skip_new_buys (bool), briefing (str),
    market_education (dict), daily_lesson (dict).
    Raises ValueError if block not found or JSON is invalid.
    """
    match = re.search(r"<decisions>(.*?)</decisions>", raw_output, re.DOTALL)
    if not match:
        raise ValueError(
            "No <decisions>...</decisions> block found in Claude output."
        )

    raw_json = match.group(1).strip()
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON inside <decisions> block: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("Parsed JSON inside <decisions> is not a dict.")

    trades = data.get("trades")
    if trades is None:
        raise ValueError("Missing required key 'trades' in decisions JSON.")
    if not isinstance(trades, list):
        raise ValueError("'trades' must be a list.")

    skip_new_buys = data.get("skip_new_buys", False)
    if not isinstance(skip_new_buys, bool):
        raise ValueError("'skip_new_buys' must be a bool.")

    briefing = data.get("briefing", "")
    if not isinstance(briefing, str):
        raise ValueError("'briefing' must be a string.")

    return {
        "trades": trades,
        "skip_new_buys": skip_new_buys,
        "briefing": briefing,
        "market_education": data.get("market_education", {}),  # FEAT-001
        "daily_lesson": data.get("daily_lesson", {}),           # FEAT-001
    }


def call_claude(prompt: str) -> str:
    """
    Calls `claude --print <prompt>` via subprocess.
    Returns stdout string.
    Raises RuntimeError on non-zero exit or timeout.
    Timeout: 120 seconds.
    """
    try:
        result = subprocess.run(
            ["claude", "--print", prompt],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired as exc:
        proc = getattr(exc, "process", None)
        if proc is not None:
            proc.kill()
        raise RuntimeError("claude CLI timed out after 120s") from exc
    if result.returncode != 0:
        raise RuntimeError(f"claude CLI failed (exit {result.returncode}): {result.stderr[:200]}")
    return result.stdout


def run_analysis(
    market_direction: dict,
    portfolio: dict,
    screened_stocks: list[dict],
    plan_path: str = "data/run1_plan.json",
) -> dict:
    """
    Orchestrates: build_prompt → call_claude → parse_decisions → save to data/run1_plan.json.
    Returns the decisions dict.
    On any error: returns {"trades": [], "skip_new_buys": False, "briefing": "Analysis failed: <error>"}.
    Never raises.
    """
    try:
        prompt = build_prompt(market_direction, portfolio, screened_stocks)
        raw_output = call_claude(prompt)
        decisions = parse_decisions(raw_output)

        # Ensure data directory exists
        plan_dir = os.path.dirname(plan_path)
        if plan_dir:
            os.makedirs(plan_dir, exist_ok=True)

        # Save result with metadata
        payload = {
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "market_direction": market_direction.get("direction", "unknown"),
            "decisions": decisions,
        }
        with open(plan_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)

        return decisions

    except Exception as exc:  # pylint: disable=broad-except
        print(f"[claude_agent] run_analysis error: {exc}")
        return {
            "trades": [],
            "skip_new_buys": False,
            "briefing": f"Analysis failed: {exc}",
            "market_education": {},  # FEAT-001
            "daily_lesson": {},      # FEAT-001
        }
