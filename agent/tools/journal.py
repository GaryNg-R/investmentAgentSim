"""
Writes a daily journal entry as a JSON file for a given trading session.

Public surface:
    write_journal_entry(decisions, portfolio, journal_dir, date_str) -> dict(ok, reason[, path])
        Never raises. Returns {"ok": True/False, "reason": str} and on success
        also {"path": str} with the absolute path of the written file.
"""

import json
import os


def write_journal_entry(
    decisions: dict,
    portfolio: dict,
    journal_dir: str,
    date_str: str,
) -> dict:
    """Write a single dated journal entry to journal_dir. Never raises.

    Args:
        decisions:    Output dict from claude_agent.py (trades, briefing, etc.).
        portfolio:    Output dict from get_portfolio_status() (cash, positions, etc.).
        journal_dir:  Directory where the journal file should be written.
                      Created automatically if it does not exist.
        date_str:     ISO date string, e.g. "2026-06-25". Used as the filename stem.

    Returns:
        {"ok": True, "reason": "written", "path": "<absolute path>"}  on success.
        {"ok": False, "reason": "<error message>"}                     on failure.
    """
    try:
        os.makedirs(journal_dir, exist_ok=True)
    except Exception as exc:
        return {"ok": False, "reason": f"could not create journal directory: {exc}"}

    file_path = os.path.join(journal_dir, f"{date_str}.json")

    # Build the structured journal payload from the two input dicts.
    entry = {
        "date": date_str,
        "briefing": decisions.get("briefing", ""),
        "daily_lesson": decisions.get("daily_lesson", {}),
        "market_education": decisions.get("market_education", {}),
        "trades": decisions.get("trades", []),
        "outcomes": {
            "total_value": portfolio.get("total_value"),
            "cash": portfolio.get("cash"),
            "pnl_dollar": portfolio.get("pnl_dollar"),
            "pnl_pct": portfolio.get("pnl_pct"),
            "positions": portfolio.get("positions", []),
        },
    }

    try:
        with open(file_path, "w", encoding="utf-8") as fh:
            # indent=2 for readability; ensure_ascii=False preserves Traditional Chinese
            json.dump(entry, fh, indent=2, ensure_ascii=False)
    except Exception as exc:
        return {"ok": False, "reason": f"could not write journal file: {exc}"}

    return {"ok": True, "reason": "written", "path": os.path.abspath(file_path)}
