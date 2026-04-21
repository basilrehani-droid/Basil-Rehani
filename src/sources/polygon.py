"""Polygon.io news fetcher. Requires POLYGON_API_KEY. Ticker-tagged, low noise.

Docs: https://polygon.io/docs/stocks/get_v2_reference_news
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any

import requests

LOG = logging.getLogger(__name__)

POLYGON_ENDPOINT = "https://api.polygon.io/v2/reference/news"
DEFAULT_TIMEOUT = 15


def fetch_polygon(api_key: str, lookback_minutes: int = 30, limit: int = 50) -> List[Dict[str, Any]]:
    """Fetch recent news from Polygon. Returns items in canonical format."""
    if not api_key:
        LOG.info("POLYGON_API_KEY not set; skipping Polygon source")
        return []

    since = datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)
    params = {
        "apiKey": api_key,
        "published_utc.gte": since.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "order": "desc",
        "limit": limit,
        "sort": "published_utc",
    }

    try:
        resp = requests.get(POLYGON_ENDPOINT, params=params, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        LOG.warning("Polygon fetch failed: %s", e)
        return []

    try:
        data = resp.json()
    except ValueError:
        LOG.warning("Polygon returned non-JSON response")
        return []

    results = data.get("results", [])
    out = []
    for i, item in enumerate(results):
        tickers = item.get("tickers", [])
        out.append({
            "id": f"polygon-{item.get('id', i)}",
            "title": item.get("title", "").strip(),
            "source": item.get("publisher", {}).get("name", "polygon"),
            "url": item.get("article_url", ""),
            "timestamp": item.get("published_utc", ""),
            "body": item.get("description", "") or "",
            "tickers_mentioned": tickers,
        })
    LOG.info("Polygon returned %d items", len(out))
    return out
