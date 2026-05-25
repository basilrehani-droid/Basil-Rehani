"""Central config loaded from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skill"
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)


@dataclass(frozen=True)
class Config:
    # Anthropic
    anthropic_api_key: str
    claude_model: str        # high-frequency triage (cheap, runs every 15 min)
    brief_model: str         # once-daily morning brief + deep reasoning

    # Polygon
    polygon_api_key: str

    # Telegram
    telegram_bot_token: str
    telegram_chat_id: str

    # Email
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    digest_to_email: str

    # Schwab
    schwab_client_id: str
    schwab_client_secret: str
    schwab_refresh_token: str

    # Thresholds
    relevance_push_threshold: int
    relevance_digest_min: int
    market_hours_only: bool


def load_config() -> Config:
    def req(key: str) -> str:
        v = os.environ.get(key, "").strip()
        if not v:
            raise RuntimeError(f"Missing required env var: {key}")
        return v

    def opt(key: str, default: str = "") -> str:
        return os.environ.get(key, default).strip() or default

    return Config(
        anthropic_api_key=req("ANTHROPIC_API_KEY"),
        claude_model=opt("CLAUDE_MODEL", "claude-sonnet-4-6"),
        brief_model=opt("CLAUDE_BRIEF_MODEL", "claude-opus-4-7"),
        polygon_api_key=opt("POLYGON_API_KEY"),
        telegram_bot_token=opt("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=opt("TELEGRAM_CHAT_ID"),
        smtp_host=opt("SMTP_HOST", "smtp.gmail.com"),
        smtp_port=int(opt("SMTP_PORT", "587")),
        smtp_user=opt("SMTP_USER"),
        smtp_password=opt("SMTP_PASSWORD"),
        digest_to_email=opt("DIGEST_TO_EMAIL"),
        schwab_client_id=opt("SCHWAB_CLIENT_ID"),
        schwab_client_secret=opt("SCHWAB_CLIENT_SECRET"),
        schwab_refresh_token=opt("SCHWAB_REFRESH_TOKEN"),
        relevance_push_threshold=int(opt("RELEVANCE_PUSH_THRESHOLD", "7")),
        relevance_digest_min=int(opt("RELEVANCE_DIGEST_MIN", "4")),
        market_hours_only=opt("MARKET_HOURS_ONLY", "true").lower() == "true",
    )


# RSS feeds — edit this list freely. Used by both triage and the brief.
RSS_FEEDS = [
    {"name": "WSJ Markets", "url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"},
    {"name": "CNBC Top News", "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html"},
    {"name": "Seeking Alpha", "url": "https://seekingalpha.com/market_currents.xml"},
    {"name": "MarketWatch Top", "url": "http://feeds.marketwatch.com/marketwatch/topstories/"},
]


# GDELT query — tune to your priority actors and themes.
# Syntax docs: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
GDELT_QUERY = (
    "(oil OR OPEC OR Iran OR Russia OR China OR sanctions OR "
    "'central bank' OR 'interest rate' OR 'supply chain' OR Hormuz) "
    "sourcelang:eng"
)

# ── Morning-brief sources ──────────────────────────────────────────────────
# The brief runs once each weekday morning and casts a wider net than the
# 15-min triage: overnight markets + policy/politics that moves markets.

# Broader GDELT query for the brief: policy, politics, and macro on top of the
# triage themes. Covers exactly the policy surface you asked for — White House
# statements, executive orders, new rules, tariffs, foreign policy, the Fed.
BRIEF_GDELT_QUERY = (
    "(Trump OR 'White House' OR 'executive order' OR tariff OR tariffs OR "
    "'Federal Reserve' OR Fed OR Powell OR SEC OR 'foreign policy' OR sanctions OR "
    "OPEC OR China OR 'interest rate' OR inflation OR 'jobs report' OR earnings) "
    "sourcelang:eng"
)

# Policy/markets RSS feeds for the brief, in addition to RSS_FEEDS above.
# Dead feeds fail gracefully (logged + skipped), so edit freely. The Federal
# Register feed is the authoritative source for executive orders and new rules.
POLICY_FEEDS = [
    {"name": "Politico Politics", "url": "https://rss.politico.com/politics-news.xml"},
    {"name": "The Hill", "url": "https://thehill.com/news/feed/"},
    {"name": "CNBC Economy", "url": "https://www.cnbc.com/id/20910258/device/rss/rss.html"},
    {"name": "Federal Register — Presidential Docs",
     "url": "https://www.federalregister.gov/api/v1/documents.rss?conditions%5Btype%5D%5B%5D=PRESDOCU&order=newest&per_page=20"},
]

# Single-name catalyst feeds for the brief: authoritative sources where stock-moving
# events break (drug approvals, etc.). Per-holding ticker feeds are pulled separately
# in sources/ticker_news.py from your live portfolio.
CATALYST_FEEDS = [
    {"name": "FDA Press Releases",
     "url": "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/press-releases/rss.xml"},
]

# US market (NYSE/Nasdaq) full-day closures. Used to annotate briefs on holidays —
# the cron runs Mon-Fri regardless, so this flags a closed-market day. Extend yearly.
MARKET_HOLIDAYS = {
    "2026-01-01": "New Year's Day",
    "2026-01-19": "Martin Luther King Jr. Day",
    "2026-02-16": "Presidents' Day",
    "2026-04-03": "Good Friday",
    "2026-05-25": "Memorial Day",
    "2026-06-19": "Juneteenth",
    "2026-07-03": "Independence Day (observed)",
    "2026-09-07": "Labor Day",
    "2026-11-26": "Thanksgiving",
    "2026-12-25": "Christmas",
}

# Ticker -> company name, used to make per-stock Google News queries precise
# (e.g. "ServiceNow" instead of the ambiguous "NOW"). Tickers not listed fall back
# to the raw symbol. Add a line when you take a new position. Schwab doesn't return
# company names, so this is maintained by hand.
COMPANY_NAMES = {
    "NOW": "ServiceNow",
    "VEEV": "Veeva Systems",
    "NCLH": "Norwegian Cruise Line",
    "SMCI": "Super Micro Computer",
    "CEG": "Constellation Energy",
    "ADBE": "Adobe",
    "MSFT": "Microsoft",
    "UAL": "United Airlines",
}
