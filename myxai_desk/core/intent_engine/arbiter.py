"""Arbiter — decides whether to reuse a cached plan or fall through to LLM.

Conditions for plan reuse:
1. High similarity match found in case store
2. The matched case was a success
3. Context is compatible (same route labels)
4. Not a high-risk operation
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from myxai_desk.core.intent_engine import config as ie_config

if TYPE_CHECKING:
    from myxai_desk.core.intent_engine.predictor import PredictResult

log = logging.getLogger("myxai")


def maybe_reuse(
    user_text: str,
    predict_result: PredictResult,
    context: dict[str, Any] | None = None,
) -> tuple[str, list[dict] | None]:
    """Decide whether to reuse a cached plan.

    Returns ``("reuse_plan", steps)`` or ``("llm", None)``.
    """
    cfg = ie_config.get()
    sim_threshold = cfg.get("case_reuse_sim_threshold", 0.92)
    high_risk_tools = set(cfg.get("high_risk_tools", ["exec"]))

    try:
        from myxai_desk.core.intent_engine.case_store import search_similar
        matches = search_similar(user_text, top_k=1, min_sim=sim_threshold)
    except Exception:
        log.debug("[arbiter] case search failed", exc_info=True)
        return "llm", None

    if not matches:
        return "llm", None

    best = matches[0]
    sim = best.get("similarity", 0)
    outcome = best.get("outcome", "")
    plan_raw = best.get("plan_json", "[]")

    if outcome != "success":
        return "llm", None

    if sim < sim_threshold:
        return "llm", None

    # Parse plan steps
    if isinstance(plan_raw, str):
        try:
            plan_steps = json.loads(plan_raw)
        except Exception:
            return "llm", None
    else:
        plan_steps = plan_raw

    if not isinstance(plan_steps, list) or not plan_steps:
        return "llm", None

    # Route compatibility check
    case_route = best.get("route_label", "")
    current_route = ",".join(predict_result.route_labels)
    if case_route and current_route and case_route != current_route:
        return "llm", None

    # High-risk check: reject if any step uses a high-risk tool
    for step in plan_steps:
        tool = step.get("tool_name", "")
        if tool in high_risk_tools:
            log.info("[arbiter] rejecting reuse: high-risk tool %s", tool)
            return "llm", None

    log.info("[arbiter] reuse plan from case %s (sim=%.3f, steps=%d)",
             best.get("id", "?"), sim, len(plan_steps))
    return "reuse_plan", plan_steps
