"""Morning-brief email. Renders the structured brief (from reasoning.generate_morning_brief)
into an HTML + plain-text email and sends it via SMTP.

Unlike email_digest (which accumulates triage items over the day), the brief is a single
synthesized briefing generated once each morning and sent immediately."""
from __future__ import annotations

import logging
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List

import markdown as md

LOG = logging.getLogger(__name__)

# (key, display heading) in render order. headline_takeaways is rendered separately.
SECTIONS: List[tuple[str, str]] = [
    ("market_overview", "Market Overview"),
    ("policy_politics", "Policy &amp; Politics"),
    ("portfolio", "Your Portfolio"),
    ("radar", "On Your Radar"),
    ("also_relevant", "Also Relevant"),
]


def _md_to_html(text: str) -> str:
    return md.markdown(text or "", extensions=["extra", "sane_lists", "nl2br"])


def send_brief(
    brief: Dict[str, Any],
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    to_email: str,
) -> bool:
    """Render and send the morning brief. Returns True if delivered."""
    if not (smtp_user and smtp_password and to_email):
        LOG.warning("Email credentials missing; cannot send morning brief")
        return False

    date = brief.get("as_of") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    takeaways = [t for t in (brief.get("headline_takeaways") or []) if t.strip()]

    html = _render_html(brief, date, takeaways)
    text = _render_text(brief, date, takeaways)

    msg = MIMEMultipart("alternative")
    n = len(takeaways)
    msg["Subject"] = f"☀️ Morning Brief · {date}" + (f" · {n} takeaways" if n else "")
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
        LOG.error("Failed to send morning brief: %s", e)
        return False

    LOG.info("Sent morning brief for %s", date)
    return True


def send_test_email(
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    to_email: str,
) -> bool:
    """Send a minimal test email through the same SMTP path the brief uses.
    No Claude, no cost — purely a delivery check. Returns True if the server accepted it."""
    if not (smtp_user and smtp_password and to_email):
        LOG.error(
            "Missing SMTP config — need SMTP_USER, SMTP_PASSWORD, DIGEST_TO_EMAIL. "
            "user=%r to=%r password=%s",
            smtp_user, to_email, "set" if smtp_password else "MISSING",
        )
        return False

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    text = (
        f"This is a test email from your news-triage service ({now}).\n\n"
        "If you're reading this, SMTP delivery works and your morning brief "
        "will arrive here too."
    )
    html = (
        '<html><body style="font-family:-apple-system,sans-serif;color:#222">'
        '<h2>✅ Email delivery works</h2>'
        f'<p>Test message from your news-triage service · {now}.</p>'
        '<p>Your daily <b>Morning Brief</b> will arrive at this address.</p>'
        '</body></html>'
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "✅ news-triage test email"
    msg["From"] = smtp_user
    msg["To"] = to_email
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as s:
            s.starttls()
            s.login(smtp_user, smtp_password)
            s.sendmail(smtp_user, [to_email], msg.as_string())
    except smtplib.SMTPAuthenticationError as e:
        LOG.error(
            "SMTP auth failed (%s). For Gmail: enable 2FA and use a 16-char App Password, "
            "not your normal password.", e,
        )
        return False
    except Exception as e:
        LOG.error("SMTP send failed: %s", e)
        return False

    LOG.info("Test email accepted by %s -> %s", smtp_host, to_email)
    return True


def _render_text(brief: Dict[str, Any], date: str, takeaways: List[str]) -> str:
    lines = [f"MORNING BRIEF — {date}", "=" * 50, ""]
    if takeaways:
        lines.append("TAKEAWAYS")
        lines += [f"  • {t}" for t in takeaways]
        lines.append("")
    for key, heading in SECTIONS:
        body = (brief.get(key) or "").strip()
        if not body:
            continue
        # Strip HTML entity in heading for plain text
        lines.append(heading.replace("&amp;", "&").upper())
        lines.append("-" * len(heading))
        lines.append(body)
        lines.append("")
    return "\n".join(lines)


def _render_html(brief: Dict[str, Any], date: str, takeaways: List[str]) -> str:
    blocks: List[str] = []

    if takeaways:
        items = "".join(f"<li>{_escape(t)}</li>" for t in takeaways)
        blocks.append(f"""
<div style="background:#f5f7fa;border-left:4px solid #2563eb;border-radius:6px;padding:12px 18px;margin:0 0 20px">
  <div style="font-weight:700;color:#1e3a8a;margin-bottom:6px">Takeaways</div>
  <ul style="margin:0;padding-left:20px;line-height:1.6">{items}</ul>
</div>""")

    for key, heading in SECTIONS:
        body = (brief.get(key) or "").strip()
        if not body:
            continue
        blocks.append(f"""
<section style="margin:0 0 22px">
  <h3 style="margin:0 0 8px;color:#111;border-bottom:1px solid #e5e7eb;padding-bottom:4px">{heading}</h3>
  <div style="line-height:1.6;color:#222">{_md_to_html(body)}</div>
</section>""")

    return f"""
<html><body style="font-family:-apple-system,Segoe UI,sans-serif;color:#222;max-width:680px;margin:0 auto;padding:8px 16px">
<h2 style="margin:0 0 4px">☀️ Morning Brief</h2>
<p style="color:#666;margin:0 0 20px">{date}</p>
{"".join(blocks)}
<p style="color:#9ca3af;font-size:12px;margin-top:28px;border-top:1px solid #eee;padding-top:10px">
Generated by your news-triage service · four-layer framework · model-synthesized from overnight news + live portfolio.
</p>
</body></html>"""


def _escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
    )
