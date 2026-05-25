"""Cross-day dedup for the briefs.

The brief is a fresh daily synthesis, but without memory it re-surfaces stories it
already covered yesterday. This keeps a small rolling store of content hashes (with
timestamps) so each brief focuses on genuinely new items. Entries older than the
retention window are pruned, so the file stays tiny and a story can resurface if it's
still developing days later.

Separate from state.py (the triage dedup store) so the two cadences don't interfere.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from .config import DATA_DIR
from .dedupe import content_hash

LOG = logging.getLogger(__name__)

STORE = DATA_DIR / "brief_seen.json"
RETENTION_DAYS = 3


def _load() -> Dict[str, str]:
    if not STORE.exists():
        return {}
    try:
        return json.loads(STORE.read_text())
    except (OSError, ValueError):
        return {}


def _prune(seen: Dict[str, str]) -> Dict[str, str]:
    cutoff = datetime.now(timezone.utc).timestamp() - RETENTION_DAYS * 86400
    out = {}
    for h, iso in seen.items():
        try:
            if datetime.fromisoformat(iso).timestamp() >= cutoff:
                out[h] = iso
        except ValueError:
            continue
    return out


def filter_unseen(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return only items not seen in a recent brief. Does not record them — call
    mark_seen() after the brief actually sends, so a failed send doesn't suppress
    tomorrow's coverage."""
    seen = _load()
    return [it for it in items if content_hash(it.get("title", ""), it.get("body", "")) not in seen]


def mark_seen(items: List[Dict[str, Any]]) -> None:
    """Record items as covered, prune old entries, and persist."""
    seen = _prune(_load())
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for it in items:
        seen[content_hash(it.get("title", ""), it.get("body", ""))] = now
    try:
        STORE.write_text(json.dumps(seen))
    except OSError as e:
        LOG.warning("Could not persist brief_seen store: %s", e)
