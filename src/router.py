"""Route the skill's output into notification tiers.

The skill outputs items with relevance_score 4-10. We split them:
- score >= push_threshold → push to Telegram immediately
- digest_min <= score < push_threshold → queue for daily email digest
- score < digest_min → ignored (shouldn't appear; skill already filters to >= 4)
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple


def split_by_tier(
    triage_output: Dict[str, Any],
    push_threshold: int,
    digest_min: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Returns (push_items, digest_items). Always safe even if triage_output is None
    or missing keys."""
    if not triage_output:
        return [], []
    items = triage_output.get("relevant_items", []) or []
    push = [i for i in items if i.get("relevance_score", 0) >= push_threshold]
    digest = [
        i for i in items
        if digest_min <= i.get("relevance_score", 0) < push_threshold
    ]
    return push, digest
