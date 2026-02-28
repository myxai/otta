"""Golden Store — candidate lifecycle and shared utilities.

Owns: ``golden_candidates`` column backfill, candidate queries.
``golden_candidates`` table is owned by execution_radar/dao.py;
this module only reads/updates it.

Utility functions ``compute_case_key`` and ``parse_candidate_plan``
are used by both the v2 golden system and execution radar.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from myxai_desk.core.storage.sqlite import execute

log = logging.getLogger("myxai")

_TABLES_READY = False

CANDIDATE_FAIL_THRESHOLD = 3


# ── Data classes ──────────────────────────────────────────────────


@dataclass
class GoldenCandidate:
    candidate_id: str
    case_key: str
    candidate_plan_json: str
    quality_score: float
    removed_steps: int
    status: str
    used_count: int
    fail_count: int
    created_at: str
    last_used_at: Optional[str]


# ── Table init ────────────────────────────────────────────────────


def _init_tables() -> None:
    global _TABLES_READY
    if _TABLES_READY:
        return
    _backfill_candidate_columns()
    _TABLES_READY = True


def _backfill_candidate_columns() -> None:
    """Ensure golden_candidates has the extra columns needed for replay."""
    from myxai_desk.core.storage.sqlite import connect

    extras = [
        ("used_count", "INTEGER NOT NULL DEFAULT 0"),
        ("fail_count", "INTEGER NOT NULL DEFAULT 0"),
        ("last_used_at", "TEXT"),
    ]
    for col, typedef in extras:
        try:
            execute(f"SELECT {col} FROM golden_candidates LIMIT 1", readonly=True)
        except Exception:
            try:
                with connect() as conn:
                    conn.execute(
                        f"ALTER TABLE golden_candidates ADD COLUMN {col} {typedef}"
                    )
            except Exception:
                pass


# ── case_key computation ──────────────────────────────────────────


def compute_case_key(
    user_text: str,
    route_labels: list[str] | None = None,
    security_mode: str = "",
) -> str:
    """Deterministic case_key from user intent + context.

    Formula: ``sha256(route_sig | security_mode | normalized_keywords)[:24]``

    Both the execution side and the radar pipeline must call this with
    equivalent inputs so that candidates match at lookup time.
    """
    route_sig = "|".join(sorted(route_labels or []))
    tokens = re.findall(r"[\w\u4e00-\u9fff]+", (user_text or "").lower())
    norm_kw = "|".join(sorted(set(tokens)))
    raw = f"{route_sig}|{security_mode}|{norm_kw}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


# ── GoldenStore ───────────────────────────────────────────────────


class GoldenStore:
    """Candidate DB operations for the replay pipeline."""

    def __init__(self) -> None:
        _init_tables()

    def get_best_candidate(self, case_key: str) -> Optional[GoldenCandidate]:
        rows = execute(
            """SELECT * FROM golden_candidates
               WHERE case_key = ? AND status IN ('new', 'used')
               ORDER BY quality_score DESC, created_at DESC
               LIMIT 1""",
            (case_key,),
            readonly=True,
        )
        if not rows:
            return None
        r = rows[0]
        return GoldenCandidate(
            candidate_id=r["candidate_id"],
            case_key=r["case_key"],
            candidate_plan_json=(
                r.get("candidate_plan_json") or "[]"
            ),
            quality_score=r.get("quality_score", 0.0),
            removed_steps=r.get("removed_steps", 0),
            status=r.get("status", "new"),
            used_count=r.get("used_count", 0),
            fail_count=r.get("fail_count", 0),
            created_at=r["created_at"],
            last_used_at=r.get("last_used_at"),
        )

    def mark_candidate_used(self, candidate_id: str, ok: bool) -> None:
        now = _now_iso()
        if ok:
            execute(
                """UPDATE golden_candidates
                   SET status = CASE WHEN status = 'new' THEN 'used' ELSE status END,
                       used_count = used_count + 1,
                       last_used_at = ?
                   WHERE candidate_id = ?""",
                (now, candidate_id),
            )
        else:
            execute(
                """UPDATE golden_candidates
                   SET fail_count = fail_count + 1,
                       last_used_at = ?,
                       status = CASE WHEN fail_count + 1 >= ? THEN 'invalid' ELSE status END
                   WHERE candidate_id = ?""",
                (now, CANDIDATE_FAIL_THRESHOLD, candidate_id),
            )


# ── Helpers ───────────────────────────────────────────────────────


def parse_candidate_plan(candidate_plan_json: str) -> list[dict]:
    """Convert candidate storage format to plan_runner format.

    Candidates store ``args_json`` as a JSON string; plan_runner expects
    ``args`` as a dict.
    """
    raw = json.loads(candidate_plan_json) if isinstance(candidate_plan_json, str) else candidate_plan_json
    steps: list[dict] = []
    for s in raw:
        tool_name = s.get("tool_name", "")
        if not tool_name:
            continue
        args = s.get("args") or s.get("args_json", "{}")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except (json.JSONDecodeError, TypeError):
                args = {}
        steps.append({"tool_name": tool_name, "args": args})
    return steps


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
