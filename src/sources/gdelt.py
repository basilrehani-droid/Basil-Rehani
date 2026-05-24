"""GDELT DOC API fetcher. Free, no auth, global coverage.

Docs: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
"""
from __future__ import annotations

import logging
from typing import List, Dict, Any

import requests

from ..config import GDELT_QUERY

LOG = logging.getLogger(__name__)

GDELT_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"
DEFAULT_TIMEOUT = 15


def fetch_gdelt(query: str = GDELT_QUERY, maxrecords: int = 40, timespan: str = "30min") -> List[Dict[str, Any]]:
    """Fetch recent articles matching the query. Returns items in the canonical format
    our reasoning layer expects: {id, title, source, url, timestamp, body}.

    `timespan` controls how far back GDELT looks (e.g. "30min" for the 15-min triage
    cadence, "18h" for the overnight window the morning brief needs)."""
    params = {
        "query": query,
        "mode": "artlist",
        "format": "json",
        "maxrecords": maxrecords,
        "timespan": timespan,
        "sort": "datedesc",
    }

    try:
        resp = requests.get(GDELT_ENDPOINT, params=params, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        LOG.warning("GDELT fetch failed: %s", e)
        return []

    try:
        data = resp.json()
    except ValueError:
        LOG.warning("GDELT returned non-JSON response")
        return []

    articles = data.get("articles", [])
    out = []
    for i, art in enumerate(articles):
        out.append({
            "id": f"gdelt-{i}",
            "title": art.get("title", "").strip(),
            "source": art.get("domain", "gdelt"),
            "url": art.get("url", ""),
            "timestamp": art.get("seendate", ""),
            "body": "",  # GDELT DOC API doesn't return bodies
        })
    LOG.info("GDELT returned %d items", len(out))
    return out
