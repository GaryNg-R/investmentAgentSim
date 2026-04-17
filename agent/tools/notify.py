"""
notify.py — Telegram notification sender.
Reads TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from environment variables.
Never raises — logs a warning if sending fails.
"""

from __future__ import annotations

import json
import os
import ssl
import urllib.request
import urllib.error

try:
    import certifi
    _SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CONTEXT = None


def send_telegram(message: str) -> bool:
    """
    Send a message to the configured Telegram chat.
    Returns True on success, False on failure.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        print("[notify] TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set — skipping")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10, context=_SSL_CONTEXT) as resp:
            return resp.status == 200
    except Exception as exc:
        print(f"[notify] Failed to send Telegram message: {exc}")
        return False


def _esc(text: str) -> str:
    """Escape Telegram HTML special characters in LLM-controlled content."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


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
                lines.append(_esc(summary_en))
            if summary_zh:
                lines.append("")
                lines.append("<b>市場摘要</b>")
                lines.append(_esc(summary_zh))
            if sources and isinstance(sources, list):
                publishers = list(dict.fromkeys(
                    s.get("publisher", "") for s in sources
                    if isinstance(s, dict) and s.get("publisher")
                ))
                if publishers:
                    lines.append("")
                    lines.append(f"🔗 Sources: {' · '.join(_esc(p) for p in publishers)}")

    # FEAT-001: contextual bilingual daily lesson
    if daily_lesson:
        term = daily_lesson.get("term", "")
        explanation_en = daily_lesson.get("explanation_en", "")
        explanation_zh = daily_lesson.get("explanation_zh", "")
        if term and (explanation_en or explanation_zh):
            lines.append("")
            lines.append(f"<b>📚 Today's Lesson: {_esc(term)}</b>")
            if explanation_en:
                lines.append(_esc(explanation_en))
            if explanation_zh:
                lines.append("")
                lines.append(f"<b>今日課題：{_esc(term)}</b>")
                lines.append(_esc(explanation_zh))

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


def notify_run2(  # FEAT-002: added benchmark param
    executed: list[str],
    rejected: list[str],
    portfolio: dict,
    benchmark: dict | None = None,
) -> None:
    """Send run2 execution results to Telegram."""
    lines = ["<b>Investment Agent — Trades Executed</b>", ""]

    if executed:
        lines.append("<b>Executed:</b>")
        for msg in executed:
            lines.append(f"  {msg}")
    else:
        lines.append("No trades executed.")

    if rejected:
        lines.append("")
        lines.append("<b>Rejected:</b>")
        for msg in rejected:
            lines.append(f"  {msg}")

    cash = portfolio.get("cash", 0.0)
    total = portfolio.get("total_value", 0.0)
    pnl = portfolio.get("pnl_pct", 0.0)
    lines.append("")
    lines.append(f"Cash: ${cash:,.2f} | Total: ${total:,.2f} | P&amp;L: {pnl:+.2f}%")

    # FEAT-002: benchmark comparison block
    if benchmark:
        voo_total = benchmark.get("total_value", 0.0)
        deposited = benchmark.get("total_deposited", 10_000.0)
        agent_pnl = (total - deposited) / deposited * 100 if deposited else 0.0
        voo_pnl = (voo_total - deposited) / deposited * 100 if deposited else 0.0
        agent_sign = "+" if agent_pnl >= 0 else ""
        voo_sign = "+" if voo_pnl >= 0 else ""
        lines.append("")
        lines.append("<b>📊 Benchmark (VOO buy &amp; hold):</b>")
        lines.append(f"  Agent: ${total:,.0f} ({agent_sign}{agent_pnl:.1f}%)")
        lines.append(f"  VOO:   ${voo_total:,.0f} ({voo_sign}{voo_pnl:.1f}%)")
        lines.append(f"  Deposited: ${deposited:,.0f} each")
        if benchmark.get("deposit_made"):
            lines.append("  +$100 deposited to both today")

    send_telegram("\n".join(lines))


def notify_error(step: str, error: str) -> None:
    """Send an error alert to Telegram."""
    message = f"<b>Investment Agent — ERROR in {step}</b>\n\n{error}"
    send_telegram(message)
