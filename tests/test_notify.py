"""Tests for agent/tools/notify.py — FEAT-001 bilingual blocks."""

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

    assert len(sent) == 1
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

    assert len(sent) == 1
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

    assert len(sent) == 1
    msg = sent[0]
    assert "📊 Market Summary" not in msg
    assert "📚 Today's Lesson" not in msg


def test_notify_run1_handles_malformed_sources(monkeypatch):
    """notify_run1 does not crash when sources contains non-dict elements."""
    sent = []
    monkeypatch.setattr("agent.tools.notify.send_telegram", lambda msg: sent.append(msg) or True)

    notify_run1(
        briefing="ok",
        trades=[],
        market_direction="neutral",
        market_education={
            "summary_en": "Market update.",
            "summary_zh": "市場更新。",
            "sources": [None, "Reuters", {"headline": "x", "publisher": "BBC"}],
        },
    )

    assert len(sent) == 1
    msg = sent[0]
    assert "🔗 Sources: BBC" in msg
