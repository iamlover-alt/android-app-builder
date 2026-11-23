"""Append-only run log (JSONL on disk if a path is given, always kept in memory).

Logs artifact *names*, statuses and short error text only; never artifact bodies
(they may contain user data) and never environment/secret values.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

MAX_TEXT = 500


def clip(s: str, n: int = MAX_TEXT) -> str:
    return s if len(s) <= n else s[: n - 3] + "..."


class RunLog:
    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path else None
        self.events: list[dict[str, Any]] = []
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event: str, **fields: Any) -> dict[str, Any]:
        rec = {"seq": len(self.events), "ts": time.time(), "event": event, **fields}
        self.events.append(rec)
        if self.path:
            with self.path.open("a") as f:
                f.write(json.dumps(rec, default=str) + "\n")
        return rec

    def of(self, event: str) -> list[dict[str, Any]]:
        return [e for e in self.events if e["event"] == event]
