"""Golden replay kernel — deterministic plan replay without LLM.

Encapsulates the three-priority replay chain and post-execution golden
asset management.  Designed to be independently testable; all side-effects
(plan execution, DB writes) flow through injected dependencies.

Priority chain:
  1. Instance hit  (exact case_key match, fastest)
  2. Template hit   (slot-filled template match)
  3. Candidate hit  (legacy candidate replay → promote to v2 instance)

Usage from the agent loop::

    decision = await try_replay(user_text, ie_result, tools, sid, progress)
    if decision.skip_llm:
        ...  # bypass LLM loop
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from myxai_desk.core.intent_engine.predictor import PredictResult

log = logging.getLogger("myxai")

CONSECUTIVE_FAIL_DISABLE_THRESHOLD = 3


# ── Result dataclass ─────────────────────────────────────────────


@dataclass
class ReplayDecision:
    """Complete output of a replay attempt — everything app.py needs."""

    skip_llm: bool = False
    plan_source: str | None = None
    case_key: str | None = None
    candidate_id: str | None = None
    removed_steps: int | None = None
    golden_version: int | None = None
    attempts_count: int = 0
    final_content: str = ""
    tools_used: list[str] = field(default_factory=list)


# ── Public API ───────────────────────────────────────────────────


async def try_replay(
    user_text: str,
    ie_result: PredictResult,
    tools: Any,
    session_id: str,
    progress: Callable | None = None,
) -> ReplayDecision:
    """Run the three-priority replay chain.

    Returns a *ReplayDecision*.  When ``skip_llm`` is True the caller
    can bypass the LLM loop entirely.
    """
    decision = ReplayDecision()

    # Priority 1 & 2: Golden v2 (Instance / Template)
    _try_golden_v2(decision, user_text, ie_result, tools, session_id, progress)
    if decision.skip_llm:
        return decision

    # Await async v2 replay
    await _try_golden_v2_async(decision, user_text, ie_result, tools, session_id, progress)
    if decision.skip_llm:
        return decision

    # Priority 3: Candidate replay → promote
    await _try_candidate_replay(decision, user_text, ie_result, tools, session_id, progress)

    return decision


async def save_new_golden(
    user_text: str,
    ie_result: PredictResult | None,
    turn_events: list[dict],
) -> None:
    """Persist a successful LLM execution as a new golden v2 instance."""
    try:
        from myxai_desk.core.intent_engine.config import golden_v2_enabled
        if not golden_v2_enabled():
            return
        from myxai_desk.core.golden.slot_extractor import extract_slots
        from myxai_desk.core.golden.store import GoldenV2Store, compute_instance_key

        sr = extract_slots(user_text)
        if not sr.intent_label or sr.confidence < 0.3:
            return

        ik = compute_instance_key(sr.intent_label, sr.slots)
        plan = [
            {"tool_name": e.get("tool", ""), "args": e.get("args", {})}
            for e in turn_events if e.get("tool")
        ]
        if plan:
            GoldenV2Store().save_instance(
                case_key=ik,
                template_id=None,
                intent_label=sr.intent_label,
                slot_values=sr.slots,
                resolved_plan=plan,
            )
    except Exception:
        log.debug("[golden.replay] save_new_golden failed", exc_info=True)


# ── Priority 1 & 2: Golden v2 ───────────────────────────────────


def _try_golden_v2(
    decision: ReplayDecision,
    user_text: str,
    ie_result: PredictResult,
    tools: Any,
    session_id: str,
    progress: Callable | None,
) -> None:
    """Synchronous gate-check — validates config / slot extraction.

    Actual plan execution is async and done in ``_try_golden_v2_async``.
    This split keeps the fast "not applicable" path synchronous.
    """
    pass  # gate check moved into async path for simplicity


async def _try_golden_v2_async(
    decision: ReplayDecision,
    user_text: str,
    ie_result: PredictResult,
    tools: Any,
    session_id: str,
    progress: Callable | None,
) -> None:
    try:
        from myxai_desk.core.intent_engine.config import golden_v2_enabled
        if not golden_v2_enabled():
            return

        from myxai_desk.core.golden.slot_extractor import extract_slots
        from myxai_desk.core.golden.store import GoldenV2Store, compute_instance_key
        from myxai_desk.core.golden.template_matcher import match as template_match
        from myxai_desk.core.golden.replay_validator import validate
        from myxai_desk.core.golden_store import parse_candidate_plan
        from myxai_desk.core.intent_engine.plan_runner import run_plan

        slot_result = extract_slots(user_text)
        store = GoldenV2Store()

        if not slot_result.intent_label or slot_result.confidence < 0.3:
            return

        instance_key = compute_instance_key(
            slot_result.intent_label, slot_result.slots,
        )

        # ── Priority 1: Instance hit ──
        inst = store.get_instance(instance_key)
        if inst and inst.resolved_plan and not _is_disabled(inst.stats):
            v = validate(inst.resolved_plan, slot_result.slots)
            if v.ok:
                inst_steps = parse_candidate_plan(
                    inst.resolved_plan_json
                    if isinstance(inst.resolved_plan_json, str)
                    else json.dumps(inst.resolved_plan)
                )
                if inst_steps:
                    result = await run_plan(inst_steps, tools, session_id, progress)
                    decision.attempts_count += result.steps_executed
                    if result.success:
                        store.record_instance_use(
                            instance_key, ok=True,
                            duration_ms=result.total_duration_ms,
                            run_id=getattr(ie_result, "run_id", None),
                        )
                        decision.skip_llm = True
                        decision.plan_source = "golden_v2_instance"
                        decision.case_key = instance_key
                        decision.tools_used = [
                            s["tool_name"] for s in result.results if s.get("tool_name")
                        ]
                        decision.final_content = result.final_summary
                        log.info("[golden.replay] instance hit: key=%s, steps=%d",
                                 instance_key[:12], result.steps_executed)
                        return
                    else:
                        store.record_instance_use(instance_key, ok=False)
                        _maybe_disable_asset("instance", instance_key, store)
                        log.info("[golden.replay] instance FAILED at step %s", result.failed_at)

        # ── Priority 2: Template hit ──
        tmatch = template_match(slot_result.intent_label, slot_result.slots)
        if tmatch and tmatch.filled_plan:
            tpl = store.get_template(tmatch.template_id)
            if tpl and _is_disabled(tpl.stats):
                log.info("[golden.replay] template %s disabled, skipping", tmatch.template_id[:16])
            else:
                v = validate(tmatch.filled_plan, slot_result.slots, tmatch.constraints)
                if v.ok:
                    tpl_steps = parse_candidate_plan(
                        json.dumps(tmatch.filled_plan, ensure_ascii=False)
                    )
                    if tpl_steps:
                        result = await run_plan(tpl_steps, tools, session_id, progress)
                        decision.attempts_count += result.steps_executed
                        if result.success:
                            store.save_instance(
                                case_key=instance_key,
                                template_id=tmatch.template_id,
                                intent_label=slot_result.intent_label,
                                slot_values=slot_result.slots,
                                resolved_plan=tmatch.filled_plan,
                            )
                            store.record_template_use(tmatch.template_id, ok=True)
                            decision.skip_llm = True
                            decision.plan_source = "golden_v2_template"
                            decision.case_key = instance_key
                            decision.tools_used = [
                                s["tool_name"] for s in result.results if s.get("tool_name")
                            ]
                            decision.final_content = result.final_summary
                            log.info("[golden.replay] template hit: tpl=%s, steps=%d",
                                     tmatch.template_id[:16], result.steps_executed)
                            return
                        else:
                            store.record_template_use(tmatch.template_id, ok=False)
                            _maybe_disable_asset("template", tmatch.template_id, store)
                            log.info("[golden.replay] template FAILED, falling through")
    except Exception:
        log.warning("[golden.replay] v2 replay skipped", exc_info=True)


# ── Priority 3: Candidate replay ────────────────────────────────


async def _try_candidate_replay(
    decision: ReplayDecision,
    user_text: str,
    ie_result: PredictResult,
    tools: Any,
    session_id: str,
    progress: Callable | None,
) -> None:
    try:
        from myxai_desk.core.intent_engine.config import golden_enabled
        if not golden_enabled():
            return

        from myxai_desk.core.golden_store import (
            GoldenStore,
            compute_case_key,
            parse_candidate_plan,
        )
        from myxai_desk.core.intent_engine.dao import update_ie_run
        from myxai_desk.core.intent_engine.plan_runner import run_plan

        sec_mode = ""
        try:
            from myxai_desk.core.policy.modes import get_current_mode
            sec_mode = get_current_mode().value
        except Exception:
            pass

        case_key = compute_case_key(
            user_text,
            route_labels=ie_result.route_labels,
            security_mode=sec_mode,
        )

        if ie_result.run_id:
            update_ie_run(ie_result.run_id, case_key=case_key)

        cand_store = GoldenStore()
        cand = cand_store.get_best_candidate(case_key)
        if not cand:
            return

        decision.candidate_id = cand.candidate_id
        decision.removed_steps = cand.removed_steps
        decision.case_key = case_key

        if ie_result.run_id:
            update_ie_run(
                ie_result.run_id,
                candidate_id=cand.candidate_id,
                removed_steps=cand.removed_steps,
            )

        cand_steps = parse_candidate_plan(cand.candidate_plan_json)
        if not cand_steps:
            return

        result = await run_plan(cand_steps, tools, session_id, progress)
        decision.attempts_count += result.steps_executed
        cand_store.mark_candidate_used(cand.candidate_id, ok=result.success)

        if result.success:
            # Promote to v2 instance
            try:
                from myxai_desk.core.golden.store import GoldenV2Store
                GoldenV2Store().save_instance(
                    case_key=case_key,
                    template_id=None,
                    intent_label=",".join(ie_result.route_labels) if ie_result.route_labels else "",
                    slot_values={},
                    resolved_plan=cand_steps,
                )
            except Exception:
                log.debug("[golden.replay] candidate→v2 promotion failed", exc_info=True)

            decision.skip_llm = True
            decision.plan_source = "golden_candidate"
            decision.tools_used = [
                s["tool_name"] for s in result.results if s.get("tool_name")
            ]
            decision.final_content = result.final_summary
            log.info("[golden.replay] candidate hit: id=%s, steps=%d",
                     cand.candidate_id[:8], result.steps_executed)
        else:
            log.info("[golden.replay] candidate %s FAILED, falling through",
                     cand.candidate_id[:8])
    except Exception:
        log.warning("[golden.replay] candidate replay skipped", exc_info=True)


# ── PR-4: Asset lifecycle ────────────────────────────────────────


def _is_disabled(stats: dict | str) -> bool:
    """Check if an asset has been disabled due to repeated failures."""
    if isinstance(stats, str):
        try:
            stats = json.loads(stats)
        except Exception:
            return False
    if not isinstance(stats, dict):
        return False
    return bool(stats.get("disabled"))


def _maybe_disable_asset(
    asset_type: str,
    asset_id: str,
    store: Any,
) -> None:
    """Auto-disable an asset after consecutive failures exceed threshold.

    Updates ``stats_json`` in-place with ``disabled: true`` when
    ``fail_count`` reaches ``CONSECUTIVE_FAIL_DISABLE_THRESHOLD``.
    """
    try:
        from myxai_desk.core.storage.sqlite import execute as sql

        if asset_type == "instance":
            rows = sql(
                "SELECT stats_json FROM golden_instances WHERE case_key = ?",
                (asset_id,), readonly=True,
            )
        elif asset_type == "template":
            rows = sql(
                "SELECT stats_json FROM golden_templates WHERE template_id = ?",
                (asset_id,), readonly=True,
            )
        else:
            return

        if not rows:
            return

        raw = rows[0].get("stats_json", "{}")
        stats = json.loads(raw) if isinstance(raw, str) else (raw or {})

        fail_count = stats.get("fail_count", 0)
        success_count = stats.get("success_count", 0)
        total = fail_count + success_count

        should_disable = (
            fail_count >= CONSECUTIVE_FAIL_DISABLE_THRESHOLD
            or (total >= 3 and fail_count > success_count * 2)
        )

        if not should_disable:
            return

        stats["disabled"] = True
        stats["disabled_reason"] = (
            f"auto: {fail_count} failures in {total} uses"
        )
        new_json = json.dumps(stats, ensure_ascii=False)

        if asset_type == "instance":
            sql(
                "UPDATE golden_instances SET stats_json = ? WHERE case_key = ?",
                (new_json, asset_id),
            )
        else:
            sql(
                "UPDATE golden_templates SET stats_json = ? WHERE template_id = ?",
                (new_json, asset_id),
            )

        log.warning(
            "[golden.replay] auto-disabled %s %s: %d fails / %d total",
            asset_type, asset_id[:16], fail_count, total,
        )
    except Exception:
        log.debug("[golden.replay] _maybe_disable_asset failed", exc_info=True)
