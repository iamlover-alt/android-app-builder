"""Failure memory: error signature -> fix. The Build Doctor looks here before any model call.

A signature is a hash of the normalised error text (paths, line numbers, hex ids and quoted
literals removed) so the same Gradle/Kotlin/R8 error in a different project maps to one entry.
The store is one JSON file; it holds error text and patches only, never prompts or secrets
(secret-looking strings are refused on write).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

from .paths import SECRET_RE, patch_path_errors

_PATH = re.compile(r"(?:file://)?(?:/[\w.\-@+]+)+(?:\.\w+)?|\b[\w\-]+(?:/[\w.\-]+)+\.\w+")
_LOC = re.compile(r":\d+(?::\d+)?")
_QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"|`[^`]*`")
_TRAILING_ID = re.compile(r":\s*[A-Za-z_][\w.<>]*\s*$")
_HEX = re.compile(r"\b[0-9a-fA-F]{8,}\b")
_NUM = re.compile(r"\b\d+\b")
_WS = re.compile(r"\s+")
MAX_LINES = 5
MAX_ENTRIES = 500


def normalise(error: str) -> str:
    t = _PATH.sub("<path>", error)
    t = _LOC.sub("", t)
    t = _QUOTED.sub("<q>", t)
    t = _TRAILING_ID.sub(": <id>", t)
    t = _HEX.sub("<hex>", t)
    t = _NUM.sub("<n>", t)
    return _WS.sub(" ", t).strip().lower()


def signature(errors: Iterable[str]) -> str:
    """Stable id for a build failure: the first few distinct normalised error lines, hashed."""
    lines = sorted(dict.fromkeys(n for e in errors if (n := normalise(e))))[:MAX_LINES]
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()[:16]


@dataclass
class FixEntry:
    signature: str
    sample: str                      # one normalised error line, for humans
    diagnosis: str
    patches: list[dict[str, str]]    # {path, find, replace}
    hits: int = 0                    # times the stored fix turned the build green
    misses: int = 0                  # times it was applied and did not

    def usable(self) -> bool:
        return not (self.misses >= 2 and self.misses > self.hits)

    def to_json(self) -> dict[str, Any]:
        return {"signature": self.signature, "sample": self.sample, "diagnosis": self.diagnosis,
                "patches": self.patches, "hits": self.hits, "misses": self.misses}


@dataclass
class FailureMemory:
    path: Path | None = None         # None = in-memory only (tests)
    entries: dict[str, FixEntry] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.path is not None:
            self.path = Path(self.path)
            if self.path.exists():
                self._load()

    def _load(self) -> None:
        """Corrupt file or entry => ignored. Entries are re-checked like fresh writes (the file is untrusted)."""
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8")).get("entries", [])
        except (OSError, ValueError, AttributeError):
            return
        for d in raw:
            try:
                e = FixEntry(**d)
                ok = (isinstance(e.patches, list) and e.patches
                      and all(isinstance(p, dict) and set(p) == {"path", "find", "replace"}
                              and all(isinstance(v, str) for v in p.values()) and not patch_path_errors(p["path"])
                              for p in e.patches)
                      and not SECRET_RE.search(json.dumps(e.to_json()))
                      and isinstance(e.hits, int) and isinstance(e.misses, int))
            except (TypeError, ValueError):
                continue
            if ok:
                self.entries[e.signature] = e

    def lookup(self, errors: Sequence[str]) -> FixEntry | None:
        e = self.entries.get(signature(errors))
        return e if e and e.usable() else None

    def record(self, errors: Sequence[str], diagnosis: str, patches: Sequence[dict[str, str]]) -> FixEntry:
        sample = next((n for e in errors if (n := normalise(e))), "")
        if SECRET_RE.search(json.dumps([diagnosis, list(patches), sample, list(errors)])):
            raise ValueError("refusing to store a fix that contains secret-looking text")
        for p in patches:
            if patch_path_errors(p["path"]):
                raise ValueError(f"refusing to store a fix for unsafe path {p['path']!r}")
        sig = signature(errors)
        old = self.entries.get(sig)
        entry = FixEntry(sig, sample[:200], diagnosis[:500], [dict(p) for p in patches],
                         hits=old.hits if old else 0, misses=0)
        self.entries[sig] = entry
        self._trim()
        self.save()
        return entry

    def mark(self, sig: str, hit: bool) -> None:
        e = self.entries.get(sig)
        if e:
            if hit:
                e.hits += 1
            else:
                e.misses += 1
            self.save()

    def _trim(self) -> None:
        while len(self.entries) > MAX_ENTRIES:  # drop the least proven entry
            worst = min(self.entries.values(), key=lambda e: (e.hits - e.misses, e.hits))
            del self.entries[worst.signature]

    def save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps({"entries": [e.to_json() for e in self.entries.values()]}, indent=1, sort_keys=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(tmp, self.path)
