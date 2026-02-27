"""Intent predictor — classifies user text and filters tool definitions.

PR-1: rule-based routing.
PR-2+: augmented with case retrieval hints.
PR-3+: augmented with plan reuse via arbiter.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from myxai_desk.core.intent_engine import config as ie_config
from myxai_desk.core.intent_engine.categories import classify, collect_tools
from myxai_desk.core.intent_engine.dao import insert_run, update_outcome

log = logging.getLogger("myxai")


@dataclass
class PredictResult:
    """Holds the output of a single predict() call."""

    run_id: str | None = None
    route_labels: list[str] = field(default_factory=list)
    route_conf: float = 0.0
    decision_mode: str = "rule"
    allowed_tools: set[str] = field(default_factory=set)
    tools_before: int = 0
    tools_after: int = 0
    hints: str = ""
    # PR-3 plan reuse fields
    decision: str = "llm"  # llm | reuse_plan
    plan_steps: list[dict] | None = None

    # ── helper methods ─────────────────────────────────────────────

    def filter_tools(self, all_defs: list[dict]) -> list[dict]:
        """Return the subset of tool definitions matching allowed_tools."""
        if not self.allowed_tools:
            return all_defs
        return [
            d for d in all_defs
            if d.get("function", {}).get("name", "") in self.allowed_tools
        ]

    def save(self, session_id: str = "", user_text: str = "", context: dict | None = None) -> None:
        """Persist this prediction as an ie_runs row."""
        self.run_id = insert_run(
            session_id=session_id,
            user_text=user_text,
            context=context,
            route_label=",".join(self.route_labels),
            route_conf=self.route_conf,
            decision_mode=self.decision_mode,
            tool_group=list(self.allowed_tools),
            tools_before=self.tools_before,
            tools_after=self.tools_after,
        )

    def write_outcome(self, outcome: str) -> None:
        if self.run_id:
            update_outcome(self.run_id, outcome)


def predict(
    user_text: str,
    context: dict[str, Any] | None = None,
    *,
    all_tool_defs: list[dict] | None = None,
    mcp_tool_names: list[str] | None = None,
) -> PredictResult:
    """Classify intent and determine which tools are relevant.

    Returns a *PredictResult* that the caller uses to filter tool_defs
    and (later) to decide whether to reuse a cached plan.
    """
    ctx = context or {}
    result = PredictResult()

    cfg = ie_config.get()
    always_include = set(cfg.get("base_tools_always_included", []))

    # --- Step 1: rule-based classification ---
    result.route_labels = classify(user_text)
    result.route_conf = 1.0 if result.route_labels else 0.0
    result.decision_mode = "rule"

    # --- Step 2: collect allowed tools ---
    result.allowed_tools = collect_tools(
        result.route_labels,
        mcp_tool_names=mcp_tool_names,
        always_include=always_include,
    )

    if all_tool_defs is not None:
        result.tools_before = len(all_tool_defs)
        result.tools_after = len(result.filter_tools(all_tool_defs))

    # --- Step 3 (PR-2): case retrieval hints ---
    if ie_config.case_retrieval_enabled():
        try:
            from myxai_desk.core.intent_engine.case_store import retrieve_hints
            hints = retrieve_hints(
                user_text,
                route_labels=result.route_labels,
                conf=result.route_conf,
            )
            if hints:
                result.hints = hints
        except Exception:
            log.debug("[ie] case retrieval skipped", exc_info=True)

    # --- Step 4 (PR-3): plan reuse arbitration ---
    if ie_config.plan_reuse_enabled():
        try:
            from myxai_desk.core.intent_engine.arbiter import maybe_reuse
            decision, plan_steps = maybe_reuse(user_text, result, ctx)
            if decision == "reuse_plan" and plan_steps:
                result.decision = "reuse_plan"
                result.plan_steps = plan_steps
                result.decision_mode = "case_reuse"
        except Exception:
            log.debug("[ie] plan reuse skipped", exc_info=True)

    return result
