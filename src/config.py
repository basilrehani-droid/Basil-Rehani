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
    claude_model: str

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


# RSS feeds — edit this list freely. Three defaults to start.
RSS_FEEDS = [
    {"name": "WSJ Markets", "url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"},
    {"name": "CNBC Top News", "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html"},
    {"name": "Seeking Alpha", "url": "https://seekingalpha.com/market_currents.xml"},
]


# GDELT query — tune to your priority actors and themes.
# Syntax docs: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
GDELT_QUERY = (
    "(oil OR OPEC OR Iran OR Russia OR China OR sanctions OR "
    "'central bank' OR 'interest rate' OR 'supply chain' OR Hormuz) "
    "sourcelang:eng"
)
