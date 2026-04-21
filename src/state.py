"""State persistence — survives across GitHub Actions runs by being committed back to the repo.

The state file is intentionally small and human-readable so diffs in git are useful.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Set

from .config import DATA_DIR

STATE_FILE = DATA_DIR / "state.json"

# Bound the seen-hash set so it doesn't grow unbounded. 7 days of market activity
# typically produces well under this many unique items.
MAX_SEEN_HASHES = 5000


@dataclass
class State:
    last_run_iso: str = ""
    seen_hashes: list = field(default_factory=list)  # Ordered; newest at end

    def mark_seen(self, content_hash: str) -> None:
        if content_hash in self.seen_hashes:
            # Move to end so it's counted as recent (prevents eviction)
            self.seen_hashes.remove(content_hash)
        self.seen_hashes.append(content_hash)
        # Evict oldest if over budget
        if len(self.seen_hashes) > MAX_SEEN_HASHES:
            self.seen_hashes = self.seen_hashes[-MAX_SEEN_HASHES:]

    def has_seen(self, content_hash: str) -> bool:
        return content_hash in set(self.seen_hashes)

    def stamp_run(self) -> None:
        self.last_run_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_state() -> State:
    if not STATE_FILE.exists():
        return State()
    with STATE_FILE.open() as f:
        data = json.load(f)
    return State(
        last_run_iso=data.get("last_run_iso", ""),
        seen_hashes=data.get("seen_hashes", []),
    )


def save_state(state: State) -> None:
    STATE_FILE.write_text(json.dumps(asdict(state), indent=2))
