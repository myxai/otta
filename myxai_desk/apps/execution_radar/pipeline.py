"""Daily execution radar pipeline: Extract → Normalize → Verify → Aggregate → Report.

Each stage is a pure function operating on intermediate data structures so that
individual steps can be retried or tested in isolation.

**Data flow**: sessions.json → tasks (with steps from audit.events) → metrics.
The pipeline extracts tool execution data *directly* from sessions.json's
``audit.events`` and ``steps`` fields — no dependency on ``exec_steps`` table.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from myxai_desk.apps.execution_radar.dao import (
    delete_date_data,
    save_daily_metrics,
    upsert_candidates,
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
    _enrich_steps_with_progress(tasks, date_str)
    tasks = verify(tasks)

    candidates = generate_candidates(tasks, date_str)
    metrics = aggregate(tasks, date_str, candidates)

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

    if candidates:
        upsert_candidates(candidates)

    # Writeback: sync effective_count → ie_runs.effective_steps
    _sync_effective_steps_to_ie_runs(tasks)

    # Golden 2.0: attempt auto template generation after new data
    _templates_created = 0
    try:
        from myxai_desk.core.intent_engine.config import golden_v2_enabled as _gv2_check
        if _gv2_check():
            from myxai_desk.core.golden.store import GoldenV2Store
            from myxai_desk.core.golden.template_generator import maybe_generate_templates
            _gv2_store = GoldenV2Store()
            _new_templates = maybe_generate_templates(_gv2_store)
            _templates_created = len(_new_templates)
            if _templates_created:
                log.info("[execution_radar] golden_v2: %d templates auto-generated", _templates_created)
    except Exception:
        log.debug("[execution_radar] golden_v2 template generation skipped", exc_info=True)

    log.info(
        "[execution_radar] pipeline done for %s — %d tasks, %d with steps, %d candidates, %d templates",
        date_str, len(tasks),
        sum(1 for t in tasks if t.get("total_steps", 0) > 0),
        len(candidates),
        _templates_created,
    )
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


# ── Pre-verify: enrich with exec_steps progress ───────────────────


def _enrich_steps_with_progress(tasks: list[dict], date_str: str) -> None:
    """Merge ``progress`` from exec_steps into pipeline task steps.

    exec_steps carries per-step progress (0/1) from the progress detector,
    but pipeline steps (extracted from sessions.json) lack this field.
    Without it, verify() always falls back to the legacy distinct-tool
    heuristic — which undercounts effective steps for single-tool-type
    tasks and makes multi_task ratio stay at 0.
    """
    try:
        from myxai_desk.apps.execution_radar.dao import get_exec_steps_for_date
        exec_rows = get_exec_steps_for_date(date_str)
    except Exception:
        return
    if not exec_rows:
        return

    by_session: dict[str, list[dict]] = {}
    for row in exec_rows:
        sid = row.get("session_id", "")
        if sid:
            by_session.setdefault(sid, []).append(row)

    enriched = 0
    for task in tasks:
        sid = task.get("session_id", "")
        es_list = by_session.get(sid)
        if not es_list:
            continue

        task_steps = task.get("steps", [])
        if not task_steps:
            continue

        es_idx = 0
        for ts in task_steps:
            tool = ts.get("tool_name", "")
            while es_idx < len(es_list):
                es = es_list[es_idx]
                if es.get("tool_name") == tool:
                    prog = es.get("progress", -1)
                    if prog >= 0:
                        ts["progress"] = prog
                        enriched += 1
                    es_idx += 1
                    break
                es_idx += 1

    if enriched:
        log.info("[execution_radar] enriched %d steps with progress data", enriched)


# ── Stage 3: Verify ────────────────────────────────────────────────


def verify(tasks: list[dict]) -> list[dict]:
    """Apply success / hit_rate / effective judgement to each task.

    Definitions:
    - **success**: whether the task ultimately completed (last step ok).
    - **effective_count**: when progress data is available, count steps with
      progress==1; otherwise fall back to the legacy distinct-tool-type method.
    - **hit_rate**: effective_count / total_steps.
    - **single** task: successful & effective_count == 1.
    - **multi** task: successful & effective_count > 1.
    - Ineffective steps get error_code ``E_RETRY``.
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
            has_progress = any(s.get("progress", -1) >= 0 for s in steps)
            if has_progress:
                effective_count, effective_indices = _compute_effective_by_progress(steps)
            else:
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


def _compute_effective_by_progress(steps: list[dict]) -> tuple[int, set[int]]:
    """Count steps where progress == 1 as effective."""
    effective_indices = {i for i, s in enumerate(steps) if s.get("progress") == 1}
    return len(effective_indices), effective_indices


def _compute_effective_steps(steps: list[dict]) -> tuple[int, set[int]]:
    """Legacy: each unique tool type contributes 1 effective step — the LAST
    occurrence of that tool in the sequence."""
    last_index_by_tool: dict[str, int] = {}
    for i, s in enumerate(steps):
        tool = s.get("tool_name", "")
        if tool:
            last_index_by_tool[tool] = i

    effective_indices = set(last_index_by_tool.values())
    return len(effective_indices), effective_indices


# ── Stage 4: Aggregate ─────────────────────────────────────────────


def aggregate(tasks: list[dict], date_str: str, candidates: list[dict] | None = None) -> dict:
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

    cands = candidates or []
    candidates_generated = len(cands)
    avg_removed_steps = (
        round(sum(c.get("removed_steps", 0) for c in cands) / len(cands), 1)
        if cands else 0.0
    )
    total_llm_saveable = sum(c.get("llm_calls_saved", 0) for c in cands)

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
        "avg_removed_steps": avg_removed_steps,
        "candidates_generated": candidates_generated,
        "total_llm_saveable": total_llm_saveable,
    }


# ── Stage 4b: Candidate Golden Path Generation ────────────────────


def generate_candidates(tasks: list[dict], date_str: str) -> list[dict]:
    """Generate candidate golden paths from successful tasks.

    Any successful task with at least one tool call is a valid candidate.
    The value of a candidate is LLM bypass — replaying the stored plan
    next time saves ≥2 LLM calls and thousands of tokens.

    Deduplicates by ``case_key`` (keep best quality_score).
    """
    from myxai_desk.apps.execution_radar.candidate import (
        candidate_metrics,
        make_candidate,
        plan_to_json,
        steps_from_dicts,
    )

    raw: list[dict] = []

    for task in tasks:
        if not task.get("success"):
            continue
        step_dicts = task.get("steps", [])
        if not step_dicts:
            continue

        steps = steps_from_dicts(step_dicts)
        plan = make_candidate(steps)
        if not plan:
            continue

        metrics = candidate_metrics(steps, plan)
        llm_saved = metrics["llm_calls_saved"]
        removed = metrics["removed_steps"]

        case_key = _generate_case_key(task, step_dicts)
        quality = round(
            2.0 * llm_saved
            + 1.0 * removed
            + 0.5 * len(plan)
            + (1.0 if task.get("hit_rate", 0) >= 1.0 else 0),
            2,
        )

        raw.append({
            "candidate_id": uuid4().hex[:16],
            "case_key": case_key,
            "source_run_id": task.get("task_id", ""),
            "candidate_plan_json": json.dumps(plan_to_json(plan), ensure_ascii=False),
            "quality_score": quality,
            "removed_steps": removed,
            "llm_calls_saved": llm_saved,
            "original_steps": len(step_dicts),
            "user_text": (task.get("user_text", "") or "")[:200],
            "created_at": f"{date_str}T00:00:00",
            "status": "new",
        })

    candidates = _dedup_candidates(raw)

    log.info(
        "[execution_radar] generated %d candidates (%d before dedup) "
        "from %d successful tasks",
        len(candidates), len(raw),
        sum(1 for t in tasks if t.get("success")),
    )
    return candidates


# ── dedup & case key ───────────────────────────────────────────────


def _dedup_candidates(candidates: list[dict]) -> list[dict]:
    """Keep only the best candidate per case_key."""
    best: dict[str, dict] = {}
    for c in candidates:
        key = c["case_key"]
        if key not in best or c["quality_score"] > best[key]["quality_score"]:
            best[key] = c
    return list(best.values())


def _generate_case_key(task: dict, steps: list[dict]) -> str:
    """Deterministic key aligned with ``golden_store.compute_case_key``.

    Uses route_labels (from intent classifier) + security_mode + normalized
    keywords so that the execution side can compute the same key at lookup time.
    Falls back to the old tools-based key if classification is unavailable.
    """
    user_text = task.get("user_text", "") or ""

    try:
        from myxai_desk.core.golden_store import compute_case_key
        from myxai_desk.core.intent_engine.categories import classify

        route_labels = classify(user_text)
        sec_mode = ""
        try:
            from myxai_desk.core.policy.modes import get_current_mode
            sec_mode = get_current_mode().value
        except Exception:
            pass
        return compute_case_key(user_text, route_labels, sec_mode)
    except Exception:
        pass

    tool_names = sorted({s.get("tool_name", "") for s in steps if s.get("tool_name")})
    tools_sig = "|".join(tool_names)
    tokens = re.findall(r"[\w\u4e00-\u9fff]+", user_text.lower())
    norm_kw = "|".join(sorted(set(tokens)))
    raw = f"{tools_sig}::{norm_kw}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


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

    prompt = f"""你是执行质量分析助手。请根据以下结构化数据，生成一段简短的"执行棱镜日报"（2-3 段，总计不超过 200 字）。

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
        from myxai_desk.core.config_service import get_config
        
        config = get_config()  # Use config_service which merges keyring secrets
        model = config.get("agents", {}).get("defaults", {}).get("model")
        if not model:
            return None
            
        # Use nanobot's matching logic to find the right provider
        from nanobot.config.loader import load_config
        nb_config = load_config()  # This returns a Config object
        provider_name = nb_config.get_provider_name(model)
        
        if not provider_name:
            return None
            
        # Get the actual config with decrypted keys from config_service
        providers = config.get("providers", {})
        p_cfg = providers.get(provider_name, {})
        api_key = p_cfg.get("apiKey", "")
        
        if not api_key or api_key == "<<KEYRING>>":
            return None
            
        return {
            "model": model,
            "api_key": api_key,
            "api_base": p_cfg.get("apiBase"),
        }
    except Exception:
        return None


# ── ie_runs writeback ──────────────────────────────────────────────


def _sync_effective_steps_to_ie_runs(tasks: list[dict]) -> None:
    """Write pipeline-computed effective_count back to ie_runs.effective_steps.

    This makes the pipeline the single source of truth for effective_steps.
    Matching strategy: session_id + user_text prefix (ie_runs truncates at 2000).
    """
    writeback = [
        (t["session_id"], (t.get("user_text") or "")[:2000], t.get("effective_count", 0))
        for t in tasks
        if t.get("session_id") and t.get("effective_count") is not None
    ]
    if not writeback:
        return

    updated = 0
    try:
        from myxai_desk.core.intent_engine.dao import init_ie_tables
        from myxai_desk.core.storage.sqlite import execute as sql

        init_ie_tables()
        for session_id, user_text, eff_count in writeback:
            try:
                result = sql(
                    """UPDATE ie_runs
                       SET effective_steps = ?
                       WHERE session_id = ?
                         AND SUBSTR(user_text, 1, 200) = SUBSTR(?, 1, 200)""",
                    (eff_count, session_id, user_text),
                )
                if result is not None:
                    updated += 1
            except Exception:
                pass
        if updated:
            log.info("[execution_radar] synced effective_steps to %d ie_runs rows", updated)
    except Exception:
        log.debug("[execution_radar] ie_runs effective_steps writeback failed", exc_info=True)
