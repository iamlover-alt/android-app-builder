"""Schema registry: validates artifact handoffs against schemas/<name>.schema.json."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

DEFAULT_SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"
SUFFIX = ".schema.json"


class SchemaRegistry:
    def __init__(self, schema_dir: Path | str = DEFAULT_SCHEMA_DIR) -> None:
        self.schema_dir = Path(schema_dir)
        self._validators: dict[str, Draft202012Validator] = {}
        for p in sorted(self.schema_dir.glob(f"*{SUFFIX}")):
            schema = json.loads(p.read_text())
            Draft202012Validator.check_schema(schema)
            self._validators[p.name[: -len(SUFFIX)]] = Draft202012Validator(schema)

    def has(self, name: str) -> bool:
        return name in self._validators

    def names(self) -> list[str]:
        return sorted(self._validators)

    def errors(self, name: str, instance: Any) -> list[str]:
        """Human-readable validation errors (empty list means valid)."""
        v = self._validators[name]
        return [
            f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}"
            for e in sorted(v.iter_errors(instance), key=lambda e: list(map(str, e.absolute_path)))
        ]
