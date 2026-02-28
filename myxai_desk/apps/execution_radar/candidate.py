"""Candidate Golden Path extraction algorithm.

Given a sequence of execution steps from a successful task, extract the
replayable path (the "candidate golden path"):

1. Remove failed/retry steps
2. De-duplicate identical steps (same normalised tool+args)
3. Keep the ordered sequence of effective tool calls

The goal is NOT step-count reduction but LLM bypass: any successful tool
execution sequence — even a single step — can be replayed next time
WITHOUT calling LLM, saving both latency and tokens.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Optional


# ── Data model ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class Step:
    """One execution step (tool call).

    status values:
      ``OK``    – succeeded
      ``E_RETRY`` – retriable failure (timeout, transient)
      ``FAIL``  – non-retriable failure
    """
    idx: int
    tool: str
    args: Any
    status: str
    verdict: Optional[str] = None
    error: Optional[str] = None


# ── Normalisation helpers ──────────────────────────────────────────

_WS_RE = re.compile(r"\s+")
_QUOTED_RE = re.compile(
    r'"([^"\\]*(?:\\.[^"\\]*)*)"|\'([^\'\\]*(?:\\.[^\'\\]*)*)\'',
)
_NUM_RE = re.compile(r"\b\d+\b")
_DATE_RE = re.compile(r"\b(20\d{2}[-/]\d{1,2}[-/]\d{1,2})\b")
_HEX_RE = re.compile(r"\b0x[0-9a-fA-F]+\b")
_GUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}"
    r"-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b",
)
_WIN_PATH_RE = re.compile(r"(?i)\b([a-z]:\\[^:*?\"<>|\r\n]+)")
_URL_RE = re.compile(r"(?i)\bhttps?://[^\s]+")


def _sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8", errors="ignore")).hexdigest()


def normalize_tool_name(tool: str) -> str:
    return (tool or "").strip().lower()


def normalize_args(tool: str, args: Any) -> str:
    """Stable, comparable string for args — volatile tokens replaced."""
    tool_n = normalize_tool_name(tool)

    if args is None:
        raw = ""
    elif isinstance(args, (dict, list)):
        raw = json.dumps(args, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    else:
        raw = str(args)

    raw = raw.strip()
    raw = _WS_RE.sub(" ", raw)

    raw = _GUID_RE.sub("<GUID>", raw)
    raw = _HEX_RE.sub("<HEX>", raw)
    raw = _DATE_RE.sub("<DATE>", raw)

    def _norm_url(m: re.Match) -> str:
        url = m.group(0)
        parts = url.split("://", 1)
        scheme = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ""
        host, *path_parts = rest.split("/", 1)
        host = host.lower()
        path = path_parts[0] if path_parts else ""
        if not path:
            return f"{scheme}://{host}/<PATH>"
        segs = path.split("/")
        first = segs[0]
        remainder = "/".join(segs[1:]) if len(segs) > 1 else ""
        return f"{scheme}://{host}/{first}/<H:{_sha1(remainder)[:8]}>"

    raw = _URL_RE.sub(_norm_url, raw)

    def _norm_path(m: re.Match) -> str:
        p = m.group(1).replace("/", "\\")
        drive = p[:2].upper()
        rest = p[2:].lstrip("\\")
        if not rest:
            return f"{drive}\\<ROOT>"
        segs = rest.split("\\")
        top = segs[0]
        remainder = "\\".join(segs[1:]) if len(segs) > 1 else ""
        return f"{drive}\\{top}\\<H:{_sha1(remainder)[:8]}>"

    raw = _WIN_PATH_RE.sub(_norm_path, raw)

    raw = _NUM_RE.sub("<N>", raw)

    if tool_n in {"exec", "shell", "cmd"}:
        raw = _normalize_exec_command(raw)

    return raw


def _normalize_exec_command(cmd: str) -> str:
    c = _WS_RE.sub(" ", cmd.strip())

    def _unquote_simple(m: re.Match) -> str:
        s = m.group(1) or m.group(2) or ""
        if re.search(r"[ \t|&<>]", s):
            return m.group(0)
        return s

    c = _QUOTED_RE.sub(_unquote_simple, c)
    return c.lower()


def normalize_key(step: Step) -> str:
    """Key for "same target" matching."""
    return f"{normalize_tool_name(step.tool)}::{normalize_args(step.tool, step.args)}"


# ── Tool classification ────────────────────────────────────────────

PROBE_TOOLS = frozenset({
    "web_search", "smart_fetch", "fetch", "http_get",
    "read_file", "list_dir", "stat", "get", "query", "search",
})

WRITE_TOOLS = frozenset({
    "write_file", "append_file", "edit_file", "delete_file",
    "move_file", "copy_file", "mkdir", "submit",
    "post", "http_post", "http_put",
})

_EXEC_PROBE_VERBS = (
    "dir", "ls", "wmic", "fsutil", "get-psdrive", "type", "cat",
    'powershell -command "get-', "powershell -command get-",
)
_EXEC_WRITE_VERBS = (
    "del ", "erase ", "rm ", "move ", "copy ", "mkdir ", "rmdir ",
    "ren ", "rename ", "set-content", "add-content",
)


def is_probe_step(step: Step) -> bool:
    t = normalize_tool_name(step.tool)
    if t in PROBE_TOOLS:
        return True
    if t in ("exec", "shell", "cmd"):
        cmd = normalize_args(step.tool, step.args)
        return any(cmd.startswith(v) for v in _EXEC_PROBE_VERBS)
    return False


def is_write_step(step: Step) -> bool:
    t = normalize_tool_name(step.tool)
    if t in WRITE_TOOLS:
        return True
    if t in ("exec", "shell", "cmd"):
        cmd = normalize_args(step.tool, step.args)
        return any(cmd.startswith(v) for v in _EXEC_WRITE_VERBS)
    return False


# ── Core algorithm ─────────────────────────────────────────────────


def _exists_later_success(steps: list[Step], key: str, start: int) -> bool:
    for j in range(start + 1, len(steps)):
        if steps[j].status == "OK" and normalize_key(steps[j]) == key:
            return True
    return False


def make_candidate(
    steps: list[Step],
    *,
    keep_probe_before_ok: int = 2,
) -> list[Step]:
    """Build candidate plan from a successful task's steps.

    Keep all OK steps (de-duplicated), preserving execution order.
    Even a single effective step is a valid candidate — because replaying
    it directly saves ≥2 LLM calls next time.
    """
    kept: list[Step] = []
    seen: set[str] = set()

    for step in steps:
        if step.status != "OK":
            continue
        key = normalize_key(step)
        if key in seen:
            continue
        kept.append(step)
        seen.add(key)

    return kept


# ── Metrics ────────────────────────────────────────────────────────


def candidate_metrics(original: list[Step], candidate: list[Step]) -> dict[str, Any]:
    """Compute metrics for a candidate golden path.

    The primary value metric is ``llm_calls_saved``: a standard agent loop
    needs N+1 LLM calls for N tool-call iterations (each iteration may have
    multiple tool calls but still counts as 1 LLM round).  A golden replay
    needs 0 LLM calls.  So the saving is at least 2 (one decision + one
    summary) for any task with tool calls.
    """
    cand_ids = {s.idx for s in candidate}
    candidate_steps = len(candidate)
    original_steps = len(original)
    removed = original_steps - candidate_steps
    return {
        "original_steps": original_steps,
        "candidate_steps": candidate_steps,
        "removed_steps": removed,
        "llm_calls_saved": 2 if candidate_steps > 0 else 0,
        "ok_original": sum(1 for s in original if s.status == "OK"),
        "ok_candidate": candidate_steps,
        "failed_removed": sum(
            1 for s in original
            if s.status in ("E_RETRY", "FAIL") and s.idx not in cand_ids
        ),
    }


# ── Adapter: pipeline step dicts → Step objects ────────────────────


def steps_from_dicts(step_dicts: list[dict]) -> list[Step]:
    """Convert radar pipeline step dicts into Step objects."""
    result: list[Step] = []
    for i, d in enumerate(step_dicts):
        raw_status = d.get("status", "ok")
        error_code = d.get("error_code", "")

        if raw_status == "ok" and error_code != "E_RETRY":
            status = "OK"
        elif raw_status == "retry" or error_code == "E_RETRY":
            status = "E_RETRY"
        else:
            status = "FAIL"

        args: Any = d.get("args_json", "{}")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                pass

        result.append(Step(
            idx=d.get("step_index", i),
            tool=d.get("tool_name", ""),
            args=args,
            status=status,
            verdict="有效" if d.get("effective") else "无效",
            error=error_code or None,
        ))
    return result


def plan_to_json(steps: list[Step]) -> list[dict]:
    """Export candidate steps to JSON-serialisable list for storage."""
    return [
        {
            "tool_name": normalize_tool_name(s.tool),
            "args_json": json.dumps(s.args, ensure_ascii=False, separators=(",", ":"))
                         if isinstance(s.args, (dict, list)) else str(s.args or ""),
            "action": "EXEC",
        }
        for s in steps
    ]
