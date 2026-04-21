"""Content-based deduplication across sources.

A single event (say, an OPEC announcement) will appear on multiple wires. We don't
want to push it to the user five times. The hash is based on a canonicalized title
so slightly-different-wording reports of the same event collide.
"""
from __future__ import annotations

import hashlib
import re


def _canonicalize(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace. Cheap but effective for
    catching wire-service near-duplicates. Not semantic dedup — for that we'd use
    an embedding model."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def content_hash(title: str, body: str = "") -> str:
    """Hash over canonicalized title + first 200 chars of body."""
    basis = _canonicalize(title) + " " + _canonicalize(body[:200])
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]
