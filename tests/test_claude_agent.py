"""Tests for agent/claude_agent.py — no real Claude CLI calls."""

import json
import subprocess
from unittest.mock import MagicMock

import pytest

from agent.claude_agent import build_prompt, call_claude, parse_decisions, run_analysis

# ---------------------------------------------------------------------------
# Fixtures / sample data
# ---------------------------------------------------------------------------

SAMPLE_MARKET = {
    "nasdaq_change_pct": 1.2,
    "sp500_change_pct": 0.8,
    "direction": "risk_on",
    "summary": "NASDAQ +1.2%, S&P500 +0.8% — risk_on",
}

SAMPLE_PORTFOLIO = {
    "cash": 8500.00,
    "positions": [{"ticker": "NVDA", "shares": 10, "avg_cost": 130.00}],
    "total_value": 9800.00,
    "pnl_dollar": -200.00,
    "pnl_pct": -2.0,
    "position_count": 1,
}

SAMPLE_STOCKS = [
    {
        "ticker": "NVDA",
        "score": 85,
        "price": 132.50,
        "rsi": 62.3,
        "signals": "MACD bullish, above SMA-20",
    },
    {
        "ticker": "MSFT",
        "score": 72,
        "price": 420.10,
        "rsi": 58.0,
        "signals": "above SMA-20",
    },
]

VALID_DECISIONS_JSON = json.dumps(
    {
        "trades": [
            {"action": "BUY", "ticker": "NVDA", "shares": 5, "reasoning": "Strong momentum"}
        ],
        "skip_new_buys": False,
        "briefing": "Market is risk-on. Buying NVDA.",
    }
)

VALID_DECISIONS_BLOCK = f"<decisions>{VALID_DECISIONS_JSON}</decisions>"


# ---------------------------------------------------------------------------
# Test 1: build_prompt contains required sections
# ---------------------------------------------------------------------------


def test_build_prompt_contains_required_sections():
    prompt = build_prompt(SAMPLE_MARKET, SAMPLE_PORTFOLIO, SAMPLE_STOCKS)
    assert isinstance(prompt, str)
    assert len(prompt) > 0
    assert "MARKET CONDITIONS" in prompt
    assert "CURRENT PORTFOLIO" in prompt
    assert "RISK RULES" in prompt
    assert "REQUIRED OUTPUT FORMAT" in prompt


# ---------------------------------------------------------------------------
# Test 2: parse_decisions extracts valid JSON
# ---------------------------------------------------------------------------


def test_parse_decisions_valid():
    raw = '<decisions>{"trades": [], "skip_new_buys": false, "briefing": "all good"}</decisions>'
    result = parse_decisions(raw)
    assert result["trades"] == []
    assert result["skip_new_buys"] is False
    assert result["briefing"] == "all good"


# ---------------------------------------------------------------------------
# Test 3: parse_decisions raises ValueError on missing block
# ---------------------------------------------------------------------------


def test_parse_decisions_missing_block():
    with pytest.raises(ValueError):
        parse_decisions("some output without decisions tags")


# ---------------------------------------------------------------------------
# Test 4: parse_decisions raises ValueError on invalid JSON
# ---------------------------------------------------------------------------


def test_parse_decisions_invalid_json():
    with pytest.raises(ValueError):
        parse_decisions("<decisions>not json</decisions>")


# ---------------------------------------------------------------------------
# Test 5: parse_decisions handles missing optional fields with defaults
# ---------------------------------------------------------------------------


def test_parse_decisions_missing_optional_fields():
    raw = '<decisions>{"trades": []}</decisions>'
    result = parse_decisions(raw)
    assert result["skip_new_buys"] is False
    assert result["briefing"] == ""


# ---------------------------------------------------------------------------
# Test 6: call_claude returns stdout on success (mock subprocess)
# ---------------------------------------------------------------------------


def test_call_claude_success(monkeypatch):
    expected_stdout = VALID_DECISIONS_BLOCK

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = expected_stdout
    mock_result.stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: mock_result)

    output = call_claude("test prompt")
    assert output == expected_stdout


# ---------------------------------------------------------------------------
# Test 7: call_claude raises RuntimeError on non-zero exit
# ---------------------------------------------------------------------------


def test_call_claude_failure(monkeypatch):
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = "something went wrong"

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: mock_result)

    with pytest.raises(RuntimeError):
        call_claude("test prompt")


# ---------------------------------------------------------------------------
# Test 8: run_analysis returns fallback on Claude failure
# ---------------------------------------------------------------------------


def test_run_analysis_fallback_on_error(monkeypatch, tmp_path):
    def mock_call_claude(prompt: str) -> str:
        raise RuntimeError("Claude CLI unavailable")

    monkeypatch.setattr("agent.claude_agent.call_claude", mock_call_claude)

    result = run_analysis(
        SAMPLE_MARKET,
        SAMPLE_PORTFOLIO,
        SAMPLE_STOCKS,
        db_path=str(tmp_path / "test.db"),
        plan_path=str(tmp_path / "run1_plan.json"),
    )

    assert result["trades"] == []
    assert result["skip_new_buys"] is False
    assert result["briefing"].startswith("Analysis failed")


# ---------------------------------------------------------------------------
# Test 9: run_analysis saves run1_plan.json on success
# ---------------------------------------------------------------------------


def test_run_analysis_saves_plan(monkeypatch, tmp_path):
    def mock_call_claude(prompt: str) -> str:
        return VALID_DECISIONS_BLOCK

    monkeypatch.setattr("agent.claude_agent.call_claude", mock_call_claude)

    plan_path = str(tmp_path / "run1_plan.json")
    result = run_analysis(
        SAMPLE_MARKET,
        SAMPLE_PORTFOLIO,
        SAMPLE_STOCKS,
        db_path=str(tmp_path / "test.db"),
        plan_path=plan_path,
    )

    assert result["trades"] != [] or isinstance(result["trades"], list)
    assert result["skip_new_buys"] is False
    assert result["briefing"] == "Market is risk-on. Buying NVDA."

    # Verify the plan file was saved
    assert os.path.exists(plan_path), "run1_plan.json should have been created"

    with open(plan_path, encoding="utf-8") as fh:
        saved = json.load(fh)

    assert "saved_at" in saved
    assert saved["market_direction"] == "risk_on"
    assert "decisions" in saved
    assert saved["decisions"]["briefing"] == "Market is risk-on. Buying NVDA."


# Need os for path check
import os
