"""Intent predictor — classifies user text and filters tool definitions.

PR-1: rule-based routing.
PR-2+: augmented with case retrieval hints.
PR-3+: augmented with plan reuse via arbiter.
"""

from __future__ import annotations

import logging
import time
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
    latency_ms: float = 0.0

    # ── helper methods ─────────────────────────────────────────────

    def filter_tools(self, all_defs: list[dict]) -> list[dict]:
        """Return the subset of tool definitions matching allowed_tools."""
        if not self.allowed_tools:
            return all_defs
        return [
            d for d in all_defs
            if d.get("function", {}).get("name", "") in self.allowed_tools
        ]

    def save(self, session_id: str = "", user_text: str = "", context: dict | None = None) -> str | None:
        """Persist this prediction as an ie_runs row. Returns run_id."""
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
        if self.run_id and self.latency_ms > 0:
            from myxai_desk.core.intent_engine.dao import update_ie_run
            update_ie_run(self.run_id, latency_ms=self.latency_ms)
        return self.run_id

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
    t0 = time.perf_counter()

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

    result.latency_ms = round((time.perf_counter() - t0) * 1000, 2)
    return result
