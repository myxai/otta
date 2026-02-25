"""Hash-chain audit ledger — append-only, tamper-evident log.

Each entry's hash = SHA-256(prev_hash + canonical_json(entry)),
forming a verifiable chain.  The ledger is stored as a JSONL file.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import TYPE_CHECKING, Any

from myxai_desk.core.storage.paths import AUDIT_LEDGER_FILE, ensure_dir

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class AuditEntry:
    ts: str
    app_id: str
    source: str
    mode: str
    capability: str
    args_digest: str
    result_digest: str
    decision: dict
    undo: dict
    entry_hash: str = ""
    prev_hash: str = ""


class AuditLedger:
    """Append-only hash-chain audit log."""

    def __init__(self, path: Path | None = None):
        self._path = path or AUDIT_LEDGER_FILE
        self._lock = Lock()
        self._prev_hash = self._recover_last_hash()

    def _recover_last_hash(self) -> str:
        """Read the last entry hash from the ledger file."""
        if not self._path.exists():
            return "0" * 64
        try:
            lines = self._path.read_text(encoding="utf-8").strip().splitlines()
            if lines:
                last = json.loads(lines[-1])
                return last.get("entry_hash", "0" * 64)
        except Exception:
            pass
        return "0" * 64

    @staticmethod
    def _digest(data: Any) -> str:
        raw = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _compute_hash(self, prev_hash: str, entry_dict: dict) -> str:
        canonical = json.dumps(entry_dict, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(
            (prev_hash + canonical).encode("utf-8"),
        ).hexdigest()

    def append(self, entry: AuditEntry) -> str:
        """Append *entry* to the ledger and return its hash."""
        with self._lock:
            entry.prev_hash = self._prev_hash
            d = asdict(entry)
            d.pop("entry_hash", None)
            entry.entry_hash = self._compute_hash(self._prev_hash, d)
            d["entry_hash"] = entry.entry_hash

            ensure_dir(self._path.parent)
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(json.dumps(d, ensure_ascii=False) + "\n")

            self._prev_hash = entry.entry_hash
            return entry.entry_hash

    def append_entry(
        self,
        capability: str,
        args: dict,
        action_id: str = "",
        *,
        app_id: str = "",
        source: str = "system",
        result_summary: str = "",
    ) -> str:
        """Convenience method to create and append an entry."""
        from myxai_desk.core.policy.modes import get_current_mode

        entry = AuditEntry(
            ts=datetime.now(timezone.utc).isoformat(),
            app_id=app_id,
            source=source,
            mode=get_current_mode().value,
            capability=capability,
            args_digest=self._digest(args),
            result_digest=self._digest(result_summary),
            decision={},
            undo={"action_id": action_id, "supported": bool(action_id)},
        )
        return self.append(entry)

    def verify_chain(self) -> tuple[bool, int, str]:
        """Verify the full chain.  Returns ``(ok, entries_checked, error)``."""
        if not self._path.exists():
            return True, 0, ""

        prev = "0" * 64
        count = 0
        try:
            with open(self._path, encoding="utf-8") as f:
                for line_no, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    entry = json.loads(line)
                    stored_hash = entry.pop("entry_hash", "")
                    expected_prev = entry.get("prev_hash", "")
                    if expected_prev != prev:
                        return False, count, f"Line {line_no}: prev_hash mismatch"
                    computed = self._compute_hash(prev, entry)
                    if computed != stored_hash:
                        return False, count, f"Line {line_no}: hash mismatch"
                    prev = stored_hash
                    count += 1
        except Exception as e:
            return False, count, str(e)

        return True, count, ""

    def export(self, *, format: str = "json") -> str:
        """Export the full ledger."""
        if not self._path.exists():
            return "[]" if format == "json" else ""
        text = self._path.read_text(encoding="utf-8")
        if format == "jsonl":
            return text
        entries = [json.loads(l) for l in text.strip().splitlines() if l.strip()]
        return json.dumps(entries, ensure_ascii=False, indent=2)

    def recent(self, n: int = 50) -> list[dict]:
        """Return the last *n* entries."""
        if not self._path.exists():
            return []
        lines = self._path.read_text(encoding="utf-8").strip().splitlines()
        entries = []
        for line in lines[-n:]:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return entries

    def query(
        self,
        *,
        request_id: str | None = None,
        app_id: str | None = None,
        capability: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Query audit entries with filters.

        Args:
            request_id: Filter by request_id (from undo.action_id)
            app_id: Filter by app_id
            capability: Filter by capability
            limit: Maximum number of results

        Returns:
            List of matching audit entries
        """
        if not self._path.exists():
            return []

        results = []
        lines = self._path.read_text(encoding="utf-8").strip().splitlines()

        for line in reversed(lines):  # Latest first
            if len(results) >= limit:
                break

            try:
                entry = json.loads(line)

                # Apply filters
                if request_id and entry.get("undo", {}).get("action_id") != request_id:
                    continue
                if app_id and entry.get("app_id") != app_id:
                    continue
                if capability and entry.get("capability") != capability:
                    continue

                results.append(entry)
            except json.JSONDecodeError:
                continue

        return results
