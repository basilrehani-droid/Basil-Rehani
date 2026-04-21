"""Email digest. Appends items scoring 4-6 to a daily file; a separate job (run once
per day) reads the file, formats an email, sends it, and clears the file.

This two-step design means the main triage run never blocks on SMTP, and we can
batch the whole day's watch-tier items into one readable email."""
from __future__ import annotations

import json
import logging
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, List

from ..config import DATA_DIR

LOG = logging.getLogger(__name__)

DIGEST_DIR = DATA_DIR / "digest"
DIGEST_DIR.mkdir(exist_ok=True)


def _today_file() -> Path:
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return DIGEST_DIR / f"{date}.jsonl"


def append_to_digest(items: List[Dict[str, Any]]) -> None:
    """Append watch-tier items to today's digest file. Called from main.py per run."""
    if not items:
        return
    path = _today_file()
    with path.open("a") as f:
        for item in items:
            f.write(json.dumps({
                "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "item": item,
            }) + "\n")
    LOG.info("Appended %d items to digest %s", len(items), path.name)


def build_and_send_digest(
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    to_email: str,
) -> bool:
    """Read today's digest file, send as email, then clear it. Call once per day."""
    path = _today_file()
    if not path.exists():
        LOG.info("No digest items today; skipping email")
        return True

    entries = []
    with path.open() as f:
        for line in f:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if not entries:
        return True

    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    html = _render_html(entries, date)
    text = _render_text(entries, date)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Layer-0 Triage Digest · {date} · {len(entries)} items"
    msg["From"] = smtp_user
    msg["To"] = to_email
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as s:
            s.starttls()
            s.login(smtp_user, smtp_password)
            s.sendmail(smtp_user, [to_email], msg.as_string())
    except Exception as e:
        LOG.error("Failed to send digest email: %s", e)
        return False

    # Clear the file so tomorrow starts fresh
    path.unlink()
    LOG.info("Sent digest with %d items, cleared %s", len(entries), path.name)
    return True


def _render_text(entries: List[Dict[str, Any]], date: str) -> str:
    lines = [f"Layer-0 Triage Digest — {date}", "=" * 50, ""]
    # Sort by relevance_score desc
    entries.sort(key=lambda e: e["item"].get("relevance_score", 0), reverse=True)
    for e in entries:
        item = e["item"]
        score = item.get("relevance_score", "")
        headline = item.get("headline", "")
        bias = item.get("directional_bias", "")
        tickers = ", ".join(
            t["ticker"] + ("*" if t.get("in_portfolio") else "")
            for t in item.get("affected_tickers", [])[:5]
        )
        stance = item.get("sizing_recommendation", {}).get("stance", "")
        lines.append(f"[{score}] {headline}")
        lines.append(f"    → {tickers} · {bias} · stance: {stance}")
        lines.append("")
    lines.append("—")
    lines.append("* = held in portfolio")
    return "\n".join(lines)


def _render_html(entries: List[Dict[str, Any]], date: str) -> str:
    entries.sort(key=lambda e: e["item"].get("relevance_score", 0), reverse=True)
    rows = []
    for e in entries:
        item = e["item"]
        score = item.get("relevance_score", "")
        headline = item.get("headline", "")
        bias = item.get("directional_bias", "")
        tickers = ", ".join(
            f"<b>{t['ticker']}</b>" if t.get("in_portfolio") else t["ticker"]
            for t in item.get("affected_tickers", [])[:5]
        )
        stance = item.get("sizing_recommendation", {}).get("stance", "")
        rows.append(f"""
<tr>
  <td style="padding:6px 12px;vertical-align:top;font-weight:600;color:#555">[{score}]</td>
  <td style="padding:6px 12px;vertical-align:top">
    <div>{_html_escape(headline)}</div>
    <div style="color:#666;font-size:13px;margin-top:4px">
      {tickers} · {_html_escape(bias)} · <code>{_html_escape(stance)}</code>
    </div>
  </td>
</tr>""")
    return f"""
<html><body style="font-family:-apple-system,sans-serif;color:#222;max-width:680px;margin:0 auto">
<h2>Layer-0 Triage Digest — {date}</h2>
<p style="color:#666">{len(entries)} items scoring 4–6 captured today (items ≥7 were pushed to Telegram).</p>
<table style="width:100%;border-collapse:collapse;border-top:1px solid #ddd">
{"".join(rows)}
</table>
<p style="color:#888;font-size:12px;margin-top:24px"><b>bold</b> tickers are held in your portfolio.</p>
</body></html>"""


def _html_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
    )
