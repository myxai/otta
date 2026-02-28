"""PlanRunner — execute a cached plan directly, skipping LLM planning.

Each step in the plan is executed sequentially via the agent's tool registry.
Results are validated and recorded in exec_steps for radar tracking.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

log = logging.getLogger("myxai")


@dataclass
class ExecMeta:
    """Execution metadata returned alongside plan output."""
    final_output: str = ""
    tool_calls: int = 0
    duration_ms: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class PlanResult:
    success: bool = False
    steps_executed: int = 0
    failed_at: int | None = None
    results: list[dict] = field(default_factory=list)
    final_summary: str = ""
    total_duration_ms: int = 0

    def to_exec_meta(self) -> ExecMeta:
        return ExecMeta(
            final_output=self.final_summary,
            tool_calls=self.steps_executed,
            duration_ms=self.total_duration_ms,
            errors=[
                r.get("result_preview", "")
                for r in self.results
                if not r.get("ok")
            ],
        )


async def run_plan(
    plan_steps: list[dict],
    tools: Any,
    session_id: str,
    on_progress: Callable | None = None,
) -> PlanResult:
    """Execute each step in *plan_steps* sequentially.

    Parameters
    ----------
    plan_steps : list of dicts with ``tool_name`` and optionally ``args``
    tools : the agent's tool registry (has ``.execute(name, args)`` method)
    session_id : for exec_steps recording
    on_progress : optional callback for streaming progress
    """
    result = PlanResult()
    _plan_start = time.time()

    for i, step in enumerate(plan_steps):
        tool_name = step.get("tool_name", "")
        args = step.get("args", {})
        if not tool_name:
            continue

        if on_progress:
            try:
                await on_progress(json.dumps({
                    "__tool_call__": True,
                    "name": tool_name,
                    "arguments": args,
                    "plan_step": i + 1,
                    "plan_total": len(plan_steps),
                }, ensure_ascii=False))
            except Exception:
                pass

        step_start = time.time()
        try:
            if hasattr(tools, "execute"):
                tool_result = await tools.execute(tool_name, args)
            else:
                tool_result = f"[plan_runner] tool registry missing execute method"
            ok = _validate_step(tool_name, args, tool_result)
        except Exception as e:
            tool_result = str(e)
            ok = False

        duration_ms = int((time.time() - step_start) * 1000)

        _record_step(
            session_id=session_id,
            tool_name=tool_name,
            args=args,
            result=str(tool_result)[:500],
            ok=ok,
            duration_ms=duration_ms,
        )

        result.steps_executed += 1
        result.results.append({
            "step": i,
            "tool_name": tool_name,
            "ok": ok,
            "duration_ms": duration_ms,
            "result_preview": str(tool_result)[:200],
        })

        if not ok:
            result.failed_at = i
            result.success = False
            result.total_duration_ms = int((time.time() - _plan_start) * 1000)
            result.final_summary = f"Plan failed at step {i+1}/{len(plan_steps)}: {tool_name}"
            log.warning("[plan_runner] step %d failed: %s", i, tool_name)
            return result

    result.success = True
    result.total_duration_ms = int((time.time() - _plan_start) * 1000)
    result.final_summary = f"Plan completed: {result.steps_executed}/{len(plan_steps)} steps"
    log.info("[plan_runner] plan completed successfully (%d steps)", result.steps_executed)
    return result


def _validate_step(tool_name: str, args: dict, result: Any) -> bool:
    """Basic validation that a step produced a meaningful result."""
    if result is None:
        return False
    result_str = str(result)
    if "error" in result_str.lower()[:100] and "success" not in result_str.lower()[:100]:
        return False
    if "traceback" in result_str.lower()[:200]:
        return False
    return True


def _record_step(
    session_id: str,
    tool_name: str,
    args: dict,
    result: str,
    ok: bool,
    duration_ms: int,
) -> None:
    """Write an exec_steps row for this plan step."""
    try:
        from myxai_desk.core.execution_log.event_writer import record_step
        record_step(
            session_id=session_id,
            tool_name=tool_name,
            args_json=args,
            status="ok" if ok else "soft_fail",
            error_code="" if ok else "E_PLAN_STEP",
            action="PLAN_REUSE",
            result_preview=result[:500],
            duration_ms=duration_ms,
        )
    except Exception:
        log.debug("[plan_runner] record_step failed", exc_info=True)
