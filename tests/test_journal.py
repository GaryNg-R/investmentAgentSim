"""Tests for agent/tools/journal.py — daily journal writer."""

import json
import os

import pytest

from agent.tools.journal import write_journal_entry


# Sample fixtures shared across tests
SAMPLE_DECISIONS = {
    "trades": [
        {
            "action": "BUY",
            "ticker": "AAPL",
            "conviction": "high",
            "reasoning": "Strong fundamentals and momentum.",
        }
    ],
    "skip_new_buys": False,
    "briefing": "Market opened higher on positive macro data.",
    "market_education": {
        "summary_en": "Fed held rates steady.",
        "summary_zh": "聯準會維持利率不變。",
        "sources": ["https://example.com/news"],
    },
    "daily_lesson": {
        "term": "P/E Ratio",
        "explanation_en": "Price-to-earnings ratio measures valuation.",
        "explanation_zh": "市盈率衡量估值。",
    },
}

SAMPLE_PORTFOLIO = {
    "cash": 5000.0,
    "total_value": 15000.0,
    "pnl_dollar": 500.0,
    "pnl_pct": 3.45,
    "position_count": 1,
    "positions": [
        {"ticker": "AAPL", "shares": 10, "avg_cost": 150.0}
    ],
}


def test_write_journal_entry_creates_file_with_correct_content(tmp_path):
    """write_journal_entry creates a dated JSON file with expected fields."""
    date_str = "2026-06-25"
    result = write_journal_entry(
        decisions=SAMPLE_DECISIONS,
        portfolio=SAMPLE_PORTFOLIO,
        journal_dir=str(tmp_path),
        date_str=date_str,
    )

    assert result["ok"] is True

    expected_file = tmp_path / f"{date_str}.json"
    assert expected_file.exists(), "Expected journal file was not created."

    with open(expected_file, encoding="utf-8") as f:
        content = json.load(f)

    # Check top-level keys
    assert content["date"] == date_str
    assert content["daily_lesson"]["term"] == "P/E Ratio"
    assert content["outcomes"]["total_value"] == 15000.0

    # Check that Traditional Chinese characters are preserved (not escaped)
    raw_text = expected_file.read_text(encoding="utf-8")
    assert "聯準會維持利率不變" in raw_text, "Non-ASCII characters must not be escaped."


def test_write_journal_entry_returns_path_on_success(tmp_path):
    """Result dict includes the path of the written file on success."""
    result = write_journal_entry(
        decisions=SAMPLE_DECISIONS,
        portfolio=SAMPLE_PORTFOLIO,
        journal_dir=str(tmp_path),
        date_str="2026-06-25",
    )

    assert result["ok"] is True
    assert "path" in result
    assert result["path"].endswith("2026-06-25.json")


def test_write_journal_entry_creates_journal_dir(tmp_path):
    """Journal directory is created automatically if it does not exist."""
    new_dir = str(tmp_path / "journals" / "nested")
    result = write_journal_entry(
        decisions=SAMPLE_DECISIONS,
        portfolio=SAMPLE_PORTFOLIO,
        journal_dir=new_dir,
        date_str="2026-06-25",
    )

    assert result["ok"] is True
    assert os.path.isdir(new_dir)


def test_write_journal_entry_never_raises_on_bad_dir(tmp_path):
    """Function must not raise when the journal directory cannot be created."""
    # Create a file where a directory path is expected so mkdir will fail
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("I am a file, not a directory.")

    bad_dir = str(blocker / "subdir")  # parent is a file — cannot mkdir here

    result = write_journal_entry(
        decisions=SAMPLE_DECISIONS,
        portfolio=SAMPLE_PORTFOLIO,
        journal_dir=bad_dir,
        date_str="2026-06-25",
    )

    assert result["ok"] is False
    assert "reason" in result
