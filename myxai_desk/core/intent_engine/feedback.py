"""Feedback loop — writes execution outcomes back to IE for continuous learning.

After each task execution, ``write_back`` updates ``ie_runs`` with the final
result and — when appropriate — creates or updates a case in ``ie_cases`` so
future routing decisions benefit from past experience.

Write-back conditions:
  - ``ie_runs`` is ALWAYS updated with ``final_category`` / ``final_success``.
  - ``ie_cases`` is updated only when ``success=True AND user_corrected=False``
    to avoid polluting the case store with bad samples.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from myxai_desk.core.intent_engine.dao import (
    find_case_by_key,
    update_case_stats,
    update_ie_run,
)

log = logging.getLogger("myxai")


def write_back(
    *,
    run_id: str,
    case_key: str = "",
    text_norm: str = "",
    user_text: str = "",
    final_category: str = "",
    route_label: str = "",
    execution_path: str = "",
    plan_kind: str = "",
    success: bool,
    user_corrected: bool = False,
    plan_steps: list[dict] | None = None,
) -> None:
    """Post-execution feedback: update ie_runs and optionally grow ie_cases."""

    # 1. Always update ie_runs
    run_fields: dict = {
        "final_category": final_category or route_label,
        "final_success": 1 if success else 0,
    }
    if execution_path:
        run_fields["execution_path"] = execution_path
    if user_corrected:
        run_fields["user_corrected"] = 1
    if case_key:
        run_fields["case_key"] = case_key

    try:
        update_ie_run(run_id, **run_fields)
    except Exception:
        log.warning("[feedback] ie_runs update failed for %s", run_id, exc_info=True)

    # 2. Update / create case (only on uncontested success)
    if user_corrected:
        log.debug("[feedback] skipping case write: user_corrected")
        return

    if not case_key:
        log.debug("[feedback] skipping case write: no case_key")
        return

    try:
        existing = find_case_by_key(case_key)
    except Exception:
        existing = None

    if existing:
        _update_existing_case(
            existing,
            success=success,
            execution_path=execution_path,
            plan_kind=plan_kind,
        )
    elif success and plan_steps:
        _create_new_case(
            case_key=case_key,
            user_text=user_text,
            text_norm=text_norm,
            route_label=final_category or route_label,
            plan_steps=plan_steps,
            execution_path=execution_path,
            plan_kind=plan_kind,
        )


def _update_existing_case(
    case: dict,
    *,
    success: bool,
    execution_path: str = "",
    plan_kind: str = "",
) -> None:
    """Increment success/fail counters and refresh boost fields."""
    case_id = case.get("id", "")
    if not case_id:
        return
    try:
        update_case_stats(case_id, success=success)

        if success and execution_path == "plan_reuse" and plan_kind:
            _promote_plan_kind(case_id, plan_kind)

        log.debug("[feedback] updated case %s success=%s", case_id, success)
    except Exception:
        log.warning("[feedback] case stats update failed", exc_info=True)


def _promote_plan_kind(case_id: str, plan_kind: str) -> None:
    """Upgrade best_plan_kind when a higher-tier plan succeeds."""
    _RANK = {"none": 0, "cached": 1, "candidate": 2, "golden": 3}
    from myxai_desk.core.storage.sqlite import execute
    rows = execute(
        "SELECT best_plan_kind FROM ie_cases WHERE id = ?",
        (case_id,),
        readonly=True,
    )
    if not rows:
        return
    current = (rows[0].get("best_plan_kind") or "none").lower()
    if _RANK.get(plan_kind, 0) > _RANK.get(current, 0):
        execute(
            "UPDATE ie_cases SET best_plan_kind = ? WHERE id = ?",
            (plan_kind, case_id),
        )


def _create_new_case(
    *,
    case_key: str,
    user_text: str,
    text_norm: str = "",
    route_label: str,
    plan_steps: list[dict],
    execution_path: str = "",
    plan_kind: str = "",
) -> None:
    """Save a brand-new case from a successful first execution.

    *user_text* (raw) is stored for display/audit.
    *text_norm* is used for the embedding vector so that future similarity
    searches (which also use norm_text) produce consistent scores.
    """
    try:
        from myxai_desk.core.intent_engine.case_store import save_case
        case_id = save_case(
            task_text=user_text,
            text_norm=text_norm,
            route_label=route_label,
            plan_steps=plan_steps,
            outcome="success",
        )
        if case_id:
            now = datetime.now(timezone.utc).isoformat()
            from myxai_desk.core.storage.sqlite import execute
            execute(
                """UPDATE ie_cases
                   SET case_key = ?,
                       text_norm = ?,
                       best_plan_kind = ?,
                       success_count = 1,
                       fail_count = 0,
                       plan_success_rate = 1.0,
                       last_used_at = ?
                   WHERE id = ?""",
                (case_key, text_norm, plan_kind or "none", now, case_id),
            )
            log.info("[feedback] new case %s (key=%s)", case_id, case_key)
    except Exception:
        log.warning("[feedback] new case creation failed", exc_info=True)
