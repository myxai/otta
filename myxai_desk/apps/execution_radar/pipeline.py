"""Daily execution radar pipeline: Extract → Normalize → Verify → Aggregate → Report.

Each stage is a pure function operating on intermediate data structures so that
individual steps can be retried or tested in isolation.

**Data flow**: sessions.json → tasks (with steps from audit.events) → metrics.
The pipeline extracts tool execution data *directly* from sessions.json's
``audit.events`` and ``steps`` fields — no dependency on ``exec_steps`` table.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from myxai_desk.apps.execution_radar.dao import (
    delete_date_data,
    save_daily_metrics,
    upsert_steps,
    upsert_tasks,
)

log = logging.getLogger("myxai")

_HISTORY_DIR = Path.home() / ".nanobot" / "desktop_history"


# ── Public entry point ─────────────────────────────────────────────


def run_daily_radar(run_date: str | None = None, *, skip_report: bool = False) -> dict:
    """Main entry point — called by the scheduler executor.

    *run_date* defaults to yesterday (local date).
    """
    date_str = run_date or (date.today() - timedelta(days=1)).isoformat()
    log.info("[execution_radar] pipeline start for %s", date_str)

    raw = extract(date_str)
    tasks = normalize(raw, date_str)
    tasks = verify(tasks)
    metrics = aggregate(tasks, date_str)

    if not skip_report:
        report = generate_report(metrics, tasks)
        if report:
            metrics["report_text"] = report

    delete_date_data(date_str)
    save_daily_metrics(metrics)

    if tasks:
        upsert_tasks(tasks)
        all_steps = []
        for t in tasks:
            all_steps.extend(t.get("steps", []))
        if all_steps:
            upsert_steps(all_steps)

    log.info("[execution_radar] pipeline done for %s — %d tasks, %d with steps",
             date_str, len(tasks), sum(1 for t in tasks if t.get("total_steps", 0) > 0))
    return metrics


# ── Stage 1: Extract ───────────────────────────────────────────────


def extract(date_str: str) -> dict:
    """Pull session history for the target date."""
    sessions = _load_sessions_for_date(date_str)
    log.info("[execution_radar] extract: %d sessions found for %s", len(sessions), date_str)
    return {"sessions": sessions, "date": date_str}


def _load_sessions_for_date(date_str: str) -> dict:
    """Load sessions from desktop_history that had activity on *date_str* (local date).

    Since sessions.json stores UTC timestamps but the pipeline runs on local
    dates, we compute the UTC range corresponding to the local date and match
    sessions whose ``updated_at`` falls within that range.
    """
    history_file = _HISTORY_DIR / "sessions.json"
    if not history_file.exists():
        return {}

    try:
        all_data: dict = json.loads(history_file.read_text(encoding="utf-8"))
    except Exception:
        log.warning("[execution_radar] failed to read sessions.json", exc_info=True)
        return {}

    try:
        local_start = datetime.strptime(date_str, "%Y-%m-%d")
        local_end = local_start + timedelta(days=1)
        import time as _time
        utc_offset_s = _time.timezone if _time.daylight == 0 else _time.altzone
        utc_offset = timedelta(seconds=-utc_offset_s)
        utc_start = (local_start - utc_offset).strftime("%Y-%m-%dT%H:%M:%S")
        utc_end = (local_end - utc_offset).strftime("%Y-%m-%dT%H:%M:%S")
    except Exception:
        utc_start = f"{date_str}T00:00:00"
        utc_end = f"{date_str}T23:59:59"

    def _ts_in_range(ts: str) -> bool:
        if not ts:
            return False
        return utc_start <= ts[:19] <= utc_end or ts.startswith(date_str)

    filtered: dict = {}
    for sid, sess in all_data.items():
        if _ts_in_range(sess.get("updated_at", "")) or _ts_in_range(sess.get("created_at", "")):
            filtered[sid] = sess
            continue
        for msg in sess.get("messages", []):
            ts = msg.get("timestamp", msg.get("ts", ""))
            if _ts_in_range(ts):
                filtered[sid] = sess
                break

    return filtered


# ── Stage 2: Normalize ─────────────────────────────────────────────


def normalize(raw: dict, date_str: str) -> list[dict]:
    """Split sessions into task dicts, extracting steps from audit.events.

    Data source priority:
    1. ``audit.events`` in bot messages — contains tool name, action, ok status
    2. ``steps`` in bot messages — dict items contain tool name and args
    Both are combined to build a complete picture of each tool execution.
    """
    sessions = raw.get("sessions", {})
    tasks: list[dict] = []

    for sid, sess in sessions.items():
        messages = sess.get("messages", [])
        user_msgs = [
            (i, m) for i, m in enumerate(messages)
            if m.get("role") == "user"
        ]

        if not user_msgs:
            continue

        for idx, (msg_idx, msg) in enumerate(user_msgs):
            next_user_idx = user_msgs[idx + 1][0] if idx + 1 < len(user_msgs) else len(messages)

            task_steps = _extract_steps_from_bot_messages(
                messages[msg_idx + 1:next_user_idx], sid, date_str
            )

            task_id = uuid4().hex[:16]
            msg_ts = msg.get("timestamp", msg.get("ts", ""))
            if not msg_ts:
                msg_ts = sess.get("updated_at", datetime.now(timezone.utc).isoformat())

            for si, s in enumerate(task_steps):
                s["task_id"] = task_id
                s["step_index"] = si

            tasks.append({
                "task_id": task_id,
                "session_id": sid,
                "created_at": msg_ts if msg_ts.startswith(date_str) else f"{date_str}T00:00:00",
                "user_text": (msg.get("content", "") or "")[:2000],
                "total_steps": len(task_steps),
                "attempts": len(task_steps),
                "steps": task_steps,
                "success": False,
                "hit_rate": 0.0,
                "total_tokens": 0,
                "final_error_code": "",
            })

    log.info("[execution_radar] normalize: %d tasks extracted, %d with tool steps",
             len(tasks), sum(1 for t in tasks if t.get("total_steps", 0) > 0))
    return tasks


def _extract_steps_from_bot_messages(
    bot_messages: list[dict], session_id: str, date_str: str
) -> list[dict]:
    """Extract tool execution steps from bot response messages.

    Combines ``audit.events`` (success/failure) with ``steps`` dict items
    (tool names and args) for a complete picture.
    """
    all_steps: list[dict] = []

    for m in bot_messages:
        role = m.get("role", "")
        if role not in ("assistant", "bot"):
            continue

        audit = m.get("audit", {})
        events = audit.get("events", [])
        raw_steps = m.get("steps", [])

        dict_steps = [s for s in raw_steps if isinstance(s, dict)]

        for i, ev in enumerate(events):
            tool_name = ev.get("tool", "")
            action = ev.get("action", "EXEC")
            ok = ev.get("ok", True)

            args_json = "{}"
            if i < len(dict_steps):
                ds = dict_steps[i]
                if not tool_name:
                    tool_name = ds.get("tool") or ds.get("name") or ""
                args = ds.get("args", {})
                if isinstance(args, dict):
                    try:
                        args_json = json.dumps(args, ensure_ascii=False, default=str)
                    except Exception:
                        args_json = str(args)[:500]
                elif isinstance(args, str):
                    args_json = args[:500]

            status = "ok" if ok else "error"
            error_code = ""
            if not ok:
                error_code = _classify_action_error(action, tool_name)

            all_steps.append({
                "step_id": uuid4().hex[:16],
                "task_id": "",
                "step_index": 0,
                "tool_name": tool_name,
                "args_json": args_json,
                "status": status,
                "error_code": error_code,
                "action": action,
                "duration_ms": 0,
                "result_json": "",
                "token_used": 0,
                "created_at": f"{date_str}T00:00:00",
            })

        if not events and dict_steps:
            for ds in dict_steps:
                tool_name = ds.get("tool") or ds.get("name") or ""
                args = ds.get("args", {})
                args_json = "{}"
                if isinstance(args, dict):
                    try:
                        args_json = json.dumps(args, ensure_ascii=False, default=str)
                    except Exception:
                        args_json = str(args)[:500]

                all_steps.append({
                    "step_id": uuid4().hex[:16],
                    "task_id": "",
                    "step_index": 0,
                    "tool_name": tool_name,
                    "args_json": args_json,
                    "status": "ok",
                    "error_code": "",
                    "action": "EXEC",
                    "duration_ms": 0,
                    "result_json": "",
                    "token_used": 0,
                    "created_at": f"{date_str}T00:00:00",
                })

    return all_steps


def _classify_action_error(action: str, tool_name: str) -> str:
    """Derive a simple error code from audit event data."""
    action_upper = (action or "").upper()
    if "DENY" in action_upper or "BLOCK" in action_upper:
        return "E_PERMISSION"
    if "TIMEOUT" in action_upper:
        return "E_TIMEOUT"
    if "FETCH" in action_upper or "NET" in action_upper:
        return "E_NETWORK"
    return "E_EXEC"


# ── Stage 3: Verify ────────────────────────────────────────────────


def verify(tasks: list[dict]) -> list[dict]:
    """Apply success / hit_rate / effective judgement to each task.

    Definitions (per user spec):
    - **success**: whether the task ultimately completed (last step ok).
    - **effective_count**: number of distinct tool types used.
      Same tool called multiple times = retries, only last call of each tool
      is "effective". Different tools = pipeline steps, each effective.
    - **hit_rate**: effective_count / total_steps.
    - **single** task: successful & effective_count == 1.
    - **multi** task: successful & effective_count > 1.
    - Ineffective steps get error_code ``E_RETRY`` — the tool ran but its
      result was insufficient, causing a retry.
    """
    for task in tasks:
        steps = task.get("steps", [])
        if not steps:
            task["success"] = False
            task["hit_rate"] = 0.0
            task["effective_count"] = 0
            continue

        last_ok = steps[-1].get("status") == "ok"
        task["success"] = last_ok

        if last_ok:
            effective_count, effective_indices = _compute_effective_steps(steps)
            task["effective_count"] = effective_count
            for i, s in enumerate(steps):
                s["effective"] = i in effective_indices
                if not s["effective"]:
                    s["status"] = "retry"
                    s["error_code"] = "E_RETRY"
        else:
            task["effective_count"] = 0
            for s in steps:
                s["effective"] = False

        n = task["total_steps"]
        task["hit_rate"] = (task["effective_count"] / n) if (last_ok and n > 0) else 0.0

        if not task["success"]:
            for s in reversed(steps):
                ec = s.get("error_code", "")
                if ec:
                    task["final_error_code"] = ec
                    break

    return tasks


def _compute_effective_steps(steps: list[dict]) -> tuple[int, set[int]]:
    """Determine which steps are effective.

    Rule: each unique tool type contributes 1 effective step — the LAST
    occurrence of that tool in the sequence. Repeated calls to the same tool
    are treated as retries; only the final one counts.

    Returns (effective_count, set_of_effective_indices).
    """
    last_index_by_tool: dict[str, int] = {}
    for i, s in enumerate(steps):
        tool = s.get("tool_name", "")
        if tool:
            last_index_by_tool[tool] = i

    effective_indices = set(last_index_by_tool.values())
    return len(effective_indices), effective_indices


# ── Stage 4: Aggregate ─────────────────────────────────────────────


def aggregate(tasks: list[dict], date_str: str) -> dict:
    """Compute daily aggregate metrics from verified tasks.

    Classification (per user spec):
    - **single** task: successful with effective_count == 1 (one tool type)
    - **multi** task: successful with effective_count > 1 (multiple tool types)
    - Hit rate per task = effective_count / total_steps.
    """
    instrumented = [t for t in tasks if t.get("total_steps", 0) > 0]

    total = len(tasks)
    success = sum(1 for t in instrumented if t.get("success"))

    # Classify by effective_count, not total_steps
    single_tasks = [t for t in instrumented if t.get("success") and t.get("effective_count", 0) == 1]
    multi_tasks = [t for t in instrumented if t.get("success") and t.get("effective_count", 0) > 1]

    def _avg_hit_rate(group: list[dict]) -> float:
        if not group:
            return 0.0
        return sum(t.get("hit_rate", 0.0) for t in group) / len(group)

    single_hit_rate = round(_avg_hit_rate(single_tasks) * 100, 1)
    multi_hit_rate = round(_avg_hit_rate(multi_tasks) * 100, 1)

    # Avg attempts: for single = avg(total_steps), for multi = avg(total_steps/effective_count)
    single_avg_attempts = (
        round(sum(t["total_steps"] for t in single_tasks) / len(single_tasks), 1)
        if single_tasks else 0
    )
    multi_avg_attempts = (
        round(
            sum(t["total_steps"] / t["effective_count"] for t in multi_tasks)
            / len(multi_tasks),
            1,
        )
        if multi_tasks else 0
    )
    multi_avg_effective = (
        round(sum(t["effective_count"] for t in multi_tasks) / len(multi_tasks), 1)
        if multi_tasks else 0
    )

    tool_counter: Counter[str] = Counter()
    for t in instrumented:
        for s in t.get("steps", []):
            tn = s.get("tool_name", "")
            if tn:
                tool_counter[tn] += 1

    top_tools = [
        {"tool": tool, "count": cnt}
        for tool, cnt in tool_counter.most_common(10)
    ]

    # Global averages for trend charts
    all_success = single_tasks + multi_tasks
    avg_attempts = (
        round(sum(t["total_steps"] for t in all_success) / len(all_success), 1)
        if all_success else 0
    )

    return {
        "date": date_str,
        "total_tasks": total,
        "instrumented_tasks": len(instrumented),
        "success_tasks": success,
        "single_tasks": len(single_tasks),
        "single_hits": len(single_tasks),
        "single_hit_rate": single_hit_rate,
        "single_avg_attempts": single_avg_attempts,
        "multi_tasks": len(multi_tasks),
        "multi_hits": len(multi_tasks),
        "multi_hit_rate": multi_hit_rate,
        "multi_avg_attempts": multi_avg_attempts,
        "multi_avg_effective": multi_avg_effective,
        "avg_attempts": avg_attempts,
        "top_tools": top_tools,
        "report_text": "",
    }


# ── Stage 5: Report (LLM, optional) ───────────────────────────────


def generate_report(metrics: dict, tasks: list[dict] | None = None) -> str:
    """Use LLM to generate a short execution radar report.

    The LLM only interprets structured stats — it does NOT judge success/fail.
    Returns empty string if LLM is unavailable.
    """
    model_cfg = _get_model_config_safe()
    if not model_cfg:
        return ""

    fail_samples = _pick_fail_samples(tasks or [], max_count=3)

    single_rate = f"{metrics.get('single_hit_rate', 0)}%" if metrics.get("single_tasks") else "N/A"
    multi_rate = f"{metrics.get('multi_hit_rate', 0)}%" if metrics.get("multi_tasks") else "N/A"
    instr = metrics.get("instrumented_tasks", 0)
    success_rate = (
        f"{round(metrics['success_tasks'] / instr * 100, 1)}%"
        if instr else "N/A"
    )

    prompt = f"""你是执行质量分析助手。请根据以下结构化数据，生成一段简短的"执行雷达日报"（2-3 段，总计不超过 200 字）。

要求：
- 说明昨日整体变化
- 指出最值得关注的问题
- 给出 1-2 条改进建议
- 不要自行判断成功/失败，严格基于数据

日期: {metrics['date']}
总任务数: {metrics['total_tasks']}
有工具调用的任务数: {instr}
成功率: {success_rate}
单任务命中率: {single_rate}
多任务命中率: {multi_rate}
平均尝试次数: {metrics['avg_attempts']}
Top 工具: {json.dumps(metrics.get('top_tools', []), ensure_ascii=False)}
失败样本摘要: {json.dumps(fail_samples, ensure_ascii=False)}
"""

    try:
        import os
        os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
        import litellm

        model = model_cfg["model"]
        _KNOWN = (
            "openai/", "azure/", "anthropic/", "cohere/", "huggingface/",
            "ollama/", "deepseek/", "groq/", "together_ai/", "openrouter/",
            "gemini/", "mistral/",
        )
        if not any(model.startswith(p) for p in _KNOWN) and model_cfg.get("api_base"):
            model = f"openai/{model}"

        resp = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            api_key=model_cfg["api_key"],
            api_base=model_cfg.get("api_base"),
            temperature=0.4,
            max_tokens=512,
        )
        content = resp.choices[0].message.content or ""

        usage = getattr(resp, "usage", None)
        if usage:
            try:
                from apps.llm_utils import record_tokens, record_task_usage
                record_tokens(
                    prompt_tokens=getattr(usage, "prompt_tokens", 0),
                    completion_tokens=getattr(usage, "completion_tokens", 0),
                )
                record_task_usage(
                    "app_execution_radar",
                    getattr(usage, "prompt_tokens", 0),
                    getattr(usage, "completion_tokens", 0),
                    0,
                )
            except Exception:
                pass

        return content.strip()
    except Exception:
        log.warning("[execution_radar] LLM report generation failed", exc_info=True)
        return ""


def _pick_fail_samples(tasks: list[dict], max_count: int = 3) -> list[dict]:
    """Pick a few failure samples for the LLM prompt."""
    failures = [t for t in tasks if not t.get("success") and t.get("steps")]
    samples = []
    for t in failures[:max_count]:
        last_step = t["steps"][-1] if t.get("steps") else {}
        samples.append({
            "user_text": (t.get("user_text", "") or "")[:100],
            "error_code": t.get("final_error_code", ""),
            "tool": last_step.get("tool_name", ""),
            "steps": t.get("total_steps", 0),
        })
    return samples


def _get_model_config_safe() -> dict | None:
    """Try to load model config; return None if unavailable."""
    try:
        from nanobot.config.loader import get_config_path, load_config
        config = load_config()
        model = config.agents.defaults.model
        p = config.get_provider(model)
        if not model or not p.api_key:
            return None
        return {
            "model": model,
            "api_key": p.api_key,
            "api_base": getattr(p, "api_base", None),
        }
    except Exception:
        return None
