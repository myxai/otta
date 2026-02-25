"""Simple JSON-file-backed key-value store."""

from __future__ import annotations

import json
from threading import Lock
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path


class JsonKV:
    """Thread-safe read/write of a single JSON file as ``dict``."""

    def __init__(self, path: Path):
        self._path = path
        self._lock = Lock()

    def load(self) -> dict[str, Any]:
        with self._lock:
            if self._path.exists():
                try:
                    return json.loads(self._path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    pass
            return {}

    def save(self, data: dict[str, Any]) -> None:
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def get(self, key: str, default: Any = None) -> Any:
        return self.load().get(key, default)

    def set(self, key: str, value: Any) -> None:
        data = self.load()
        data[key] = value
        self.save(data)

    def delete(self, key: str) -> None:
        data = self.load()
        data.pop(key, None)
        self.save(data)
