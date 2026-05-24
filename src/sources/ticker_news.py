"""Per-ticker news fetcher for the morning brief.

For each ticker the trader holds, pull a dedicated single-name news feed so the
brief can surface stock-specific catalysts (FDA approvals, government contracts,
M&A, guidance, rating changes) that broad market feeds miss.

Two free sources per ticker:
  - Yahoo Finance per-ticker RSS — clean, finance-scoped headlines.
  - Google News search RSS — broader catalyst coverage (government orders,
    sector-sympathy stories), recency-bounded with a `when:` operator.

Items are tagged with the ticker in `tickers_mentioned` so the reasoning layer
can attribute each headline to the right name.
"""
from __future__ import annotations

import logging
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, List

import feedparser

LOG = logging.getLogger(__name__)

YAHOO_URL = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
GOOGLE_NEWS_URL = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"


def _entries(url: str, limit: int, lookback_minutes: int) -> List[Any]:
    """Parse a feed and return up to `limit` recent entries. Entries without a
    parseable timestamp are kept (some feeds omit dates); dated entries older than
    the lookback are dropped."""
    cutoff = datetime.now(timezone.utc).timestamp() - lookback_minutes * 60
    try:
        parsed = feedparser.parse(url)
    except Exception as e:
        LOG.warning("ticker feed parse failed (%s): %s", url[:60], e)
        return []

    kept = []
    for entry in parsed.entries:
        published = entry.get("published_parsed") or entry.get("updated_parsed")
        if published and datetime(*published[:6], tzinfo=timezone.utc).timestamp() < cutoff:
            continue
        kept.append(entry)
        if len(kept) >= limit:
            break
    return kept


def _to_item(entry: Any, ticker: str, source: str, idx: int) -> Dict[str, Any]:
    published = entry.get("published_parsed") or entry.get("updated_parsed")
    ts = datetime(*published[:6], tzinfo=timezone.utc).isoformat() if published else ""
    return {
        "id": f"{source}-{ticker}-{idx}",
        "title": entry.get("title", "").strip(),
        "source": f"{source}:{ticker}",
        "url": entry.get("link", ""),
        "timestamp": ts,
        "body": (entry.get("summary") or entry.get("description") or "")[:500],
        "tickers_mentioned": [ticker],
    }


def fetch_ticker_news(
    tickers: List[str],
    names: Dict[str, str] | None = None,
    per_source: int = 4,
    lookback_minutes: int = 18 * 60,
) -> List[Dict[str, Any]]:
    """Pull recent single-name news for each ticker from Yahoo + Google News.
    `names` maps ticker -> company name to keep Google queries precise (e.g.
    "ServiceNow" instead of the ambiguous "NOW"). Returns canonical news items
    tagged with their ticker. One ticker or feed failing never blocks the others."""
    if not tickers:
        return []
    names = names or {}

    out: List[Dict[str, Any]] = []
    for ticker in tickers:
        t = ticker.strip().upper()
        if not t:
            continue

        yahoo = _entries(YAHOO_URL.format(ticker=urllib.parse.quote(t)), per_source, lookback_minutes)
        for i, e in enumerate(yahoo):
            out.append(_to_item(e, t, "yahoo", i))

        # Prefer the company name for the Google query; fall back to the raw ticker.
        query_term = names.get(t, f"{t} stock")
        q = urllib.parse.quote(f"{query_term} when:1d")
        google = _entries(GOOGLE_NEWS_URL.format(q=q), per_source, lookback_minutes)
        for i, e in enumerate(google):
            out.append(_to_item(e, t, "google", i))

    LOG.info("Ticker news: %d items across %d tickers", len(out), len(tickers))
    return out
