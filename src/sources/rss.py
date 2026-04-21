"""RSS feed fetcher. Free, near-real-time for major outlets."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Dict, Any

import feedparser

LOG = logging.getLogger(__name__)


def fetch_rss(feeds: List[Dict[str, str]], lookback_minutes: int = 30) -> List[Dict[str, Any]]:
    """Fetch items from configured RSS feeds. Filters to recent items only (since
    lookback_minutes) so we don't reprocess old content every run."""
    cutoff = datetime.now(timezone.utc).timestamp() - (lookback_minutes * 60)
    out: List[Dict[str, Any]] = []

    for feed_cfg in feeds:
        name = feed_cfg["name"]
        url = feed_cfg["url"]
        try:
            parsed = feedparser.parse(url)
        except Exception as e:
            LOG.warning("RSS fetch failed for %s: %s", name, e)
            continue

        if parsed.bozo and not parsed.entries:
            LOG.warning("RSS feed %s returned no entries (bozo=%s)", name, parsed.bozo_exception)
            continue

        for i, entry in enumerate(parsed.entries):
            # Parse timestamp
            published = entry.get("published_parsed") or entry.get("updated_parsed")
            if published:
                ts = datetime(*published[:6], tzinfo=timezone.utc).timestamp()
                if ts < cutoff:
                    continue
                timestamp_iso = datetime(*published[:6], tzinfo=timezone.utc).isoformat()
            else:
                timestamp_iso = ""

            out.append({
                "id": f"rss-{name.lower().replace(' ', '_')}-{i}",
                "title": entry.get("title", "").strip(),
                "source": name,
                "url": entry.get("link", ""),
                "timestamp": timestamp_iso,
                "body": (entry.get("summary") or entry.get("description") or "")[:500],
            })

    LOG.info("RSS returned %d items across %d feeds", len(out), len(feeds))
    return out
