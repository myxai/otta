"""Persona update audit log.

Every field-level change to the persona profile is appended to
``~/.nanobot/profile/persona_update.log`` as a JSONL line, providing
a tamper-evident trail of *who* changed *what* and *why*.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from myxai_desk.core.storage.paths import PERSONA_AUDIT_FILE, ensure_dir

MAX_ENTRIES = 5000


def record(
    *,
    layer: str,
    fields: list[str],
    source: str,
    confidence: float,
    old_values: dict | None = None,
    new_values: dict | None = None,
    reason: str = "",
) -> None:
    """Append one audit entry."""
    ensure_dir(PERSONA_AUDIT_FILE.parent)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "layer": layer,
        "fields": fields,
        "source": source,
        "confidence": round(confidence, 3),
        "reason": reason,
    }
    if old_values:
        entry["old"] = old_values
    if new_values:
        entry["new"] = new_values

    with open(PERSONA_AUDIT_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    _prune()


def recent(n: int = 100) -> list[dict]:
    """Return the last *n* audit entries (newest first)."""
    if not PERSONA_AUDIT_FILE.exists():
        return []
    lines = PERSONA_AUDIT_FILE.read_text(encoding="utf-8").strip().splitlines()
    entries: list[dict] = []
    for line in reversed(lines):
        if len(entries) >= n:
            break
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def _prune() -> None:
    """Keep the log under MAX_ENTRIES by trimming the oldest half."""
    if not PERSONA_AUDIT_FILE.exists():
        return
    lines = PERSONA_AUDIT_FILE.read_text(encoding="utf-8").strip().splitlines()
    if len(lines) <= MAX_ENTRIES:
        return
    keep = lines[len(lines) - MAX_ENTRIES:]
    PERSONA_AUDIT_FILE.write_text("\n".join(keep) + "\n", encoding="utf-8")


def clear() -> None:
    if PERSONA_AUDIT_FILE.exists():
        PERSONA_AUDIT_FILE.unlink()
