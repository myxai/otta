"""Case store — save and retrieve execution cases for the Intent Engine.

Cases are stored in ``ie_cases`` (SQLite) with vector embeddings in an
HNSW index for fast similarity search.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from myxai_desk.core.intent_engine import config as ie_config
from myxai_desk.core.intent_engine.dao import get_cases, increment_case_usage, insert_case
from myxai_desk.core.intent_engine.embedder import embed_text, get_dim
from myxai_desk.core.intent_engine.hnsw_index import add as hnsw_add
from myxai_desk.core.intent_engine.hnsw_index import count as hnsw_count
from myxai_desk.core.intent_engine.hnsw_index import init as hnsw_init
from myxai_desk.core.intent_engine.hnsw_index import search as hnsw_search

_EMBEDDING_MODEL = "text-embedding-3-small"

log = logging.getLogger("myxai")

_initialised = False


def _ensure_init() -> None:
    global _initialised
    if _initialised:
        return
    hnsw_init(dim=get_dim())
    _initialised = True


# ── Case collection ───────────────────────────────────────────────

def save_case(
    *,
    task_text: str,
    text_norm: str = "",
    route_label: str = "",
    plan_steps: list[dict] | None = None,
    outcome: str = "success",
    pitfalls: str = "",
    fail_reason: str = "",
    context_fp: str = "",
) -> str | None:
    """Persist a case and add its embedding to the HNSW index.

    *task_text* is the raw user input (stored for display/audit).
    *text_norm* is the normalised text used for embedding.  When omitted the
    raw text is used as fallback, but callers should always provide norm.
    """
    _ensure_init()

    embed_source = text_norm or task_text
    vec = embed_text(embed_source)
    if vec is None:
        log.warning("[case_store] embedding failed, skipping case")
        return None

    case_id = insert_case(
        task_text=task_text,
        context_fp=context_fp,
        route_label=route_label,
        plan_json=plan_steps,
        pitfalls=pitfalls,
        fail_reason=fail_reason,
        outcome=outcome,
        embedding_id=str(hnsw_count()),
    )
    if case_id:
        hnsw_add(case_id, vec)
        try:
            from myxai_desk.core.storage.sqlite import execute as _exec
            norm_hash = hashlib.md5(embed_source.encode()).hexdigest()[:12]
            _exec(
                """UPDATE ie_cases
                   SET text_norm = ?,
                       norm_hash = ?,
                       embedding_dim = ?,
                       embedding_model = ?
                   WHERE id = ?""",
                (text_norm, norm_hash, len(vec), _EMBEDDING_MODEL, case_id),
            )
        except Exception:
            pass
    return case_id


# ── Case retrieval ────────────────────────────────────────────────

def search_similar(
    text: str,
    top_k: int = 5,
    min_sim: float = 0.3,
) -> list[dict]:
    """Find the most similar cases to *text*."""
    _ensure_init()
    vec = embed_text(text)
    if vec is None:
        return []
    raw = hnsw_search(vec, top_k=top_k)
    if not raw:
        return []

    from myxai_desk.core.storage.sqlite import execute

    results: list[dict] = []
    for case_id, sim in raw:
        if sim < min_sim:
            continue
        rows = execute(
            "SELECT * FROM ie_cases WHERE id = ?", (case_id,), readonly=True
        )
        if rows:
            row = dict(rows[0])
            row["similarity"] = round(sim, 4)
            results.append(row)
            increment_case_usage(case_id)
    return results


def retrieve_hints(
    user_text: str,
    *,
    route_labels: list[str] | None = None,
    conf: float = 1.0,
) -> str:
    """Build hint text from similar cases when confidence is low.

    Returns an empty string if no useful hints are found.
    """
    cfg = ie_config.get()
    threshold = cfg.get("route_conf_low", 0.4)
    max_len = cfg.get("hints_max_length", 600)

    if conf > threshold and not (conf < 0.7):
        return ""

    cases = search_similar(user_text, top_k=3, min_sim=0.4)
    if not cases:
        return ""

    parts: list[str] = []
    for c in cases:
        outcome = c.get("outcome", "")
        text = c.get("task_text", "")[:80]
        pitfalls = c.get("pitfalls", "")
        fail_reason = c.get("fail_reason", "")

        if outcome == "success":
            plan = c.get("plan_json", "[]")
            if isinstance(plan, str):
                try:
                    plan = json.loads(plan)
                except Exception:
                    plan = []
            tool_seq = ", ".join(s.get("tool_name", "") for s in plan if isinstance(s, dict))
            parts.append(f"[similar task: {text}] tools: {tool_seq}")
        elif outcome == "fail" and (pitfalls or fail_reason):
            parts.append(f"[warning: {text}] pitfall: {pitfalls or fail_reason}")

    hint = "\n".join(parts)
    if len(hint) > max_len:
        hint = hint[:max_len] + "..."
    return hint
