"""Telegram bot notifier. See TELEGRAM_SETUP.md for getting a bot token + chat ID."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

import requests

LOG = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org/bot"
DEFAULT_TIMEOUT = 15
MAX_MESSAGE_LEN = 4000  # Telegram limit is 4096; leave margin


def send_alert(bot_token: str, chat_id: str, high_priority_items: List[Dict[str, Any]]) -> bool:
    """Send a compact alert for high-priority items (score >= push threshold).
    Returns True if delivered, False otherwise."""
    if not (bot_token and chat_id):
        LOG.warning("Telegram credentials missing; skipping push")
        return False
    if not high_priority_items:
        return True  # Nothing to send, not an error

    lines = ["🔔 *Layer-0 Triage*\n"]
    for item in high_priority_items:
        headline = item.get("headline", "")[:200]
        bias = item.get("directional_bias", "")
        tickers = ", ".join(
            t["ticker"] + ("⚑" if t.get("in_portfolio") else "")
            for t in item.get("affected_tickers", [])[:5]
        )
        stance = item.get("sizing_recommendation", {}).get("stance", "")
        score = item.get("relevance_score", "")
        overrides = item.get("sizing_recommendation", {}).get("overrides", [])

        block = (
            f"\n*[{score}]* {_escape(headline)}\n"
            f"→ {_escape(tickers)} · {_escape(bias)}\n"
            f"→ stance: `{stance}`"
        )
        if overrides:
            block += f"\n⚠ {_escape(overrides[0][:200])}"

        # URL if present (first ticker's item — optional; we attach the first source URL
        # via the affected_tickers ordering above; real URL lives on the item itself)
        url = item.get("url", "")
        if url:
            block += f"\n[source]({url})"

        lines.append(block)

    text = "\n".join(lines)

    # Split if too long
    chunks = _chunk(text, MAX_MESSAGE_LEN)
    ok = True
    for chunk in chunks:
        if not _send_chunk(bot_token, chat_id, chunk):
            ok = False
    return ok


def _send_chunk(bot_token: str, chat_id: str, text: str) -> bool:
    url = f"{TELEGRAM_API_BASE}{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, json=payload, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        return True
    except requests.RequestException as e:
        LOG.error("Telegram send failed: %s", e)
        return False


def _escape(text: str) -> str:
    """Escape Markdown-sensitive characters minimally. Telegram's Markdown parser is
    legacy and forgiving; we only escape the characters that commonly break formatting."""
    for ch in ["_", "*", "[", "]", "`"]:
        text = text.replace(ch, "\\" + ch)
    return text


def _chunk(text: str, limit: int) -> List[str]:
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        # Prefer to split at the last double newline before the limit
        split_at = text.rfind("\n\n", 0, limit)
        if split_at < limit // 2:
            split_at = limit
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip()
    return chunks
