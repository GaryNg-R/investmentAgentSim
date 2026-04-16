# Bilingual Market Education Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the Run 1 Telegram notification with a bilingual (English + financial Chinese) macro market summary (with cited sources) and a contextual daily finance lesson.

**Architecture:** Three files change — `claude_agent.py` gets extended prompt instructions and parser output, `notify.py` gets two new optional message blocks, `main.py` passes the new fields through. All new fields are optional/graceful: if Claude omits them, the agent runs normally. No new tools, no new Claude calls, no new dependencies. All touch points tagged `# FEAT-001`.

**Tech Stack:** Python 3.12, yfinance (news already fetched), Telegram HTML messages

---

## File Map

| File | Change |
|------|--------|
| `agent/claude_agent.py` | Extend `build_prompt()` section 6 + extend `parse_decisions()` return dict |
| `agent/tools/notify.py` | Extend `notify_run1()` signature + message body |
| `agent/main.py` | Pass new fields in `notify_run1()` call |
| `tests/test_claude_agent.py` | Add 2 new tests for FEAT-001 fields |
| `tests/test_notify.py` | Create new file with 3 tests |

---

## Task 1: Extend `build_prompt()` to request bilingual fields

**Files:**
- Modify: `agent/claude_agent.py` (section 6 of `build_prompt`)
- Test: `tests/test_claude_agent.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_claude_agent.py`:

```python
# FEAT-001
def test_build_prompt_requests_feat001_fields():
    prompt = build_prompt(SAMPLE_MARKET, SAMPLE_PORTFOLIO, SAMPLE_STOCKS)
    assert "market_education" in prompt
    assert "daily_lesson" in prompt
    assert "summary_zh" in prompt
    assert "explanation_zh" in prompt
```

- [ ] **Step 2: Run test to verify it fails**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_claude_agent.py::test_build_prompt_requests_feat001_fields -v
```

Expected: FAIL — `assert "market_education" in prompt`

- [ ] **Step 3: Replace section 6 in `build_prompt()`**

In `agent/claude_agent.py`, replace the `section6` string (starting at `# Section 6 — Output instructions`) with:

```python
    # Section 6 — Output instructions  # FEAT-001: added market_education and daily_lesson
    section6 = """\
REQUIRED OUTPUT FORMAT:
Respond with ONLY a JSON block inside <decisions> tags. No explanation before or after.

<decisions>
{
  "trades": [
    {"action": "BUY or SELL", "ticker": "TICKER", "shares": N, "reasoning": "one sentence"}
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
- skip_new_buys: set true if you think market conditions are too risky for new positions
- briefing: plain English summary, no jargon
- Only recommend tickers from the screened list
- Sell decisions: ticker must be in current portfolio
- market_education.sources: only cite headlines from the RECENT NEWS section above
- daily_lesson.term: must be derived from what actually happened today, not a random concept"""
```

- [ ] **Step 4: Run test to verify it passes**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_claude_agent.py::test_build_prompt_requests_feat001_fields -v
```

Expected: PASS

- [ ] **Step 5: Run full suite to confirm no regressions**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_claude_agent.py -v
```

Expected: All existing tests + new test pass.

- [ ] **Step 6: Commit**

```bash
git add agent/claude_agent.py tests/test_claude_agent.py
git commit -m "feat(FEAT-001): extend build_prompt to request bilingual market education fields"
```

---

## Task 2: Extend `parse_decisions()` to extract bilingual fields

**Files:**
- Modify: `agent/claude_agent.py` (`parse_decisions` return dict)
- Test: `tests/test_claude_agent.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_claude_agent.py`:

```python
# FEAT-001
def test_parse_decisions_extracts_market_education_and_daily_lesson():
    """parse_decisions returns market_education and daily_lesson when present."""
    payload = {
        "trades": [],
        "skip_new_buys": False,
        "briefing": "ok",
        "market_education": {
            "summary_en": "Markets fell on recession fears [Reuters].",
            "summary_zh": "市場因衰退憂慮下跌。",
            "sources": [{"headline": "Recession fears mount", "publisher": "Reuters"}],
        },
        "daily_lesson": {
            "term": "Risk-Off",
            "explanation_en": "Risk-off means investors flee to safer assets.",
            "explanation_zh": "避險模式指投資者轉向安全資產。",
        },
    }
    result = parse_decisions(f"<decisions>{json.dumps(payload)}</decisions>")
    assert result["market_education"]["summary_en"] == "Markets fell on recession fears [Reuters]."
    assert result["market_education"]["sources"][0]["publisher"] == "Reuters"
    assert result["daily_lesson"]["term"] == "Risk-Off"
    assert result["daily_lesson"]["explanation_zh"] == "避險模式指投資者轉向安全資產。"


# FEAT-001
def test_parse_decisions_missing_feat001_fields_returns_empty_dicts():
    """parse_decisions returns empty dicts when FEAT-001 fields are absent."""
    raw = '<decisions>{"trades": [], "skip_new_buys": false, "briefing": "ok"}</decisions>'
    result = parse_decisions(raw)
    assert result["market_education"] == {}
    assert result["daily_lesson"] == {}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_claude_agent.py::test_parse_decisions_extracts_market_education_and_daily_lesson tests/test_claude_agent.py::test_parse_decisions_missing_feat001_fields_returns_empty_dicts -v
```

Expected: FAIL — `KeyError: 'market_education'`

- [ ] **Step 3: Update `parse_decisions()` return dict**

In `agent/claude_agent.py`, replace the `return` statement at the end of `parse_decisions`:

```python
    return {
        "trades": trades,
        "skip_new_buys": skip_new_buys,
        "briefing": briefing,
        "market_education": data.get("market_education", {}),  # FEAT-001
        "daily_lesson": data.get("daily_lesson", {}),           # FEAT-001
    }
```

- [ ] **Step 4: Run new tests to verify they pass**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_claude_agent.py::test_parse_decisions_extracts_market_education_and_daily_lesson tests/test_claude_agent.py::test_parse_decisions_missing_feat001_fields_returns_empty_dicts -v
```

Expected: PASS

- [ ] **Step 5: Run full suite to confirm no regressions**

```bash
PYTHONPATH=. .venv/bin/pytest tests/ -v
```

Expected: All 69 existing tests + 3 new tests pass (72 total).

- [ ] **Step 6: Commit**

```bash
git add agent/claude_agent.py tests/test_claude_agent.py
git commit -m "feat(FEAT-001): extend parse_decisions to extract market_education and daily_lesson"
```

---

## Task 3: Extend `notify_run1()` with bilingual message blocks

**Files:**
- Modify: `agent/tools/notify.py` (`notify_run1` signature + body)
- Modify: `agent/main.py` (pass new fields in call)
- Create: `tests/test_notify.py`

- [ ] **Step 1: Create `tests/test_notify.py` with failing tests**

```python
"""Tests for agent/tools/notify.py — FEAT-001 bilingual blocks."""

import pytest
from agent.tools.notify import notify_run1


def test_notify_run1_includes_bilingual_blocks(monkeypatch):
    """notify_run1 includes market summary and daily lesson when data is present."""
    sent = []
    monkeypatch.setattr("agent.tools.notify.send_telegram", lambda msg: sent.append(msg) or True)

    notify_run1(
        briefing="Markets are strong.",
        trades=[],
        market_direction="risk_on",
        market_education={
            "summary_en": "Markets rose on strong jobs data [Reuters].",
            "summary_zh": "市場因就業數據強勁而上漲。",
            "sources": [{"headline": "Jobs surge", "publisher": "Reuters"}],
        },
        daily_lesson={
            "term": "Risk-On",
            "explanation_en": "Risk-on means investors embrace higher-risk assets.",
            "explanation_zh": "風險偏好模式指投資者傾向高風險資產。",
        },
    )

    msg = sent[0]
    assert "📊 Market Summary" in msg
    assert "Markets rose on strong jobs data" in msg
    assert "市場摘要" in msg
    assert "市場因就業數據強勁而上漲" in msg
    assert "🔗 Sources: Reuters" in msg
    assert "📚 Today's Lesson: Risk-On" in msg
    assert "Risk-on means investors embrace" in msg
    assert "今日課題：Risk-On" in msg
    assert "風險偏好模式" in msg


def test_notify_run1_skips_blocks_when_no_education_data(monkeypatch):
    """notify_run1 sends normally when market_education and daily_lesson are omitted."""
    sent = []
    monkeypatch.setattr("agent.tools.notify.send_telegram", lambda msg: sent.append(msg) or True)

    notify_run1(briefing="All good.", trades=[], market_direction="neutral")

    msg = sent[0]
    assert "Investment Agent" in msg
    assert "📊 Market Summary" not in msg
    assert "📚 Today's Lesson" not in msg


def test_notify_run1_skips_blocks_when_empty_dicts(monkeypatch):
    """notify_run1 handles empty dicts gracefully — no KeyError, no extra blocks."""
    sent = []
    monkeypatch.setattr("agent.tools.notify.send_telegram", lambda msg: sent.append(msg) or True)

    notify_run1(
        briefing="ok",
        trades=[],
        market_direction="neutral",
        market_education={},
        daily_lesson={},
    )

    msg = sent[0]
    assert "📊 Market Summary" not in msg
    assert "📚 Today's Lesson" not in msg
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_notify.py -v
```

Expected: FAIL — `TypeError: notify_run1() got unexpected keyword argument 'market_education'`

- [ ] **Step 3: Update `notify_run1()` in `agent/tools/notify.py`**

Replace the entire `notify_run1` function:

```python
def notify_run1(  # FEAT-001: added market_education and daily_lesson params
    briefing: str,
    trades: list[dict],
    market_direction: str,
    market_education: dict | None = None,
    daily_lesson: dict | None = None,
) -> None:
    """Send run1 plan summary to Telegram."""
    lines = [
        "<b>Investment Agent — Daily Plan</b>",
        f"Market: {market_direction}",
        "",
        briefing,
    ]

    # FEAT-001: bilingual macro market summary
    if market_education:
        summary_en = market_education.get("summary_en", "")
        summary_zh = market_education.get("summary_zh", "")
        sources = market_education.get("sources", [])
        if summary_en or summary_zh:
            lines.append("")
            lines.append("<b>📊 Market Summary</b>")
            if summary_en:
                lines.append(summary_en)
            if summary_zh:
                lines.append("")
                lines.append("<b>市場摘要</b>")
                lines.append(summary_zh)
            if sources:
                publishers = list(dict.fromkeys(
                    s.get("publisher", "") for s in sources if s.get("publisher")
                ))
                if publishers:
                    lines.append("")
                    lines.append(f"🔗 Sources: {' · '.join(publishers)}")

    # FEAT-001: contextual bilingual daily lesson
    if daily_lesson:
        term = daily_lesson.get("term", "")
        explanation_en = daily_lesson.get("explanation_en", "")
        explanation_zh = daily_lesson.get("explanation_zh", "")
        if term and (explanation_en or explanation_zh):
            lines.append("")
            lines.append(f"<b>📚 Today's Lesson: {term}</b>")
            if explanation_en:
                lines.append(explanation_en)
            if explanation_zh:
                lines.append("")
                lines.append(f"<b>今日課題：{term}</b>")
                lines.append(explanation_zh)

    if trades:
        lines.append("")
        lines.append("<b>Planned trades:</b>")
        for t in trades:
            action = t.get("action", "")
            ticker = t.get("ticker", "")
            shares = t.get("shares", 0)
            reasoning = t.get("reasoning", "")
            lines.append(f"  {action} {shares} {ticker} — {reasoning}")
    else:
        lines.append("")
        lines.append("No trades planned today.")

    send_telegram("\n".join(lines))
```

- [ ] **Step 4: Update the `notify_run1` call in `agent/main.py` (line 89)**

Replace:
```python
        notify_run1(decisions["briefing"], decisions.get("trades", []), market_direction["direction"])
```

With:
```python
        notify_run1(  # FEAT-001: pass bilingual education fields
            decisions["briefing"],
            decisions.get("trades", []),
            market_direction["direction"],
            market_education=decisions.get("market_education", {}),
            daily_lesson=decisions.get("daily_lesson", {}),
        )
```

- [ ] **Step 5: Run new notify tests to verify they pass**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_notify.py -v
```

Expected: 3 PASS

- [ ] **Step 6: Run full suite to confirm no regressions**

```bash
PYTHONPATH=. .venv/bin/pytest tests/ -v
```

Expected: All 72 tests pass (69 existing + 3 new in test_notify.py).

- [ ] **Step 7: Commit**

```bash
git add agent/tools/notify.py agent/main.py tests/test_notify.py
git commit -m "feat(FEAT-001): extend notify_run1 with bilingual market summary and daily lesson"
```
