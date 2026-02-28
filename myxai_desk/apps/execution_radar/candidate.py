"""Candidate Golden Path extraction algorithm.

Given a sequence of execution steps from a successful task, extract the
minimal effective path (the "candidate golden path") by:

1. Removing failed steps that have a later successful replacement
2. De-duplicating successful targets (same normalised tool+args)
3. Keeping only OK steps
4. Re-inserting minimal probe/read context before write/action steps

The normalisation layer handles volatile tokens (URLs, paths, GUIDs,
dates, numbers) so that semantically identical calls match even when
surface strings differ.
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

    1. Failed step with later identical success → drop
    2. Duplicate success (same normalised key) → drop
    3. Only keep OK steps
    4. ``ensure_preconditions``: re-insert preceding probe context
    """
    kept: list[Step] = []
    seen: set[str] = set()

    for i, step in enumerate(steps):
        key = normalize_key(step)

        if step.status in ("E_RETRY", "FAIL"):
            continue

        if step.status == "OK":
            if key in seen:
                continue
            kept.append(step)
            seen.add(key)

    return _ensure_preconditions(steps, kept, keep_probe_before_ok)


def _ensure_preconditions(
    original_steps: list[Step],
    plan: list[Step],
    context_window: int = 2,
) -> list[Step]:
    """For each non-probe kept step, re-insert up to *context_window*
    preceding OK probe steps from the original stream."""
    if not plan:
        return plan

    idx_to_step = {s.idx: s for s in original_steps}
    plan_idx_set = {s.idx for s in plan}
    idx_pos = {s.idx: pos for pos, s in enumerate(original_steps)}

    extra_probe_idxs: set[int] = set()

    for s in plan:
        if is_write_step(s) or (s.status == "OK" and not is_probe_step(s)):
            pos = idx_pos.get(s.idx)
            if pos is None:
                continue
            found = 0
            p = pos - 1
            while p >= 0 and found < context_window:
                cand = original_steps[p]
                if cand.status == "OK" and is_probe_step(cand) \
                        and cand.idx not in plan_idx_set:
                    extra_probe_idxs.add(cand.idx)
                    found += 1
                p -= 1

    merged_idxs = sorted(
        plan_idx_set | extra_probe_idxs,
        key=lambda x: idx_pos.get(x, 10**12),
    )
    merged = [idx_to_step[i] for i in merged_idxs if i in idx_to_step]
    return _dedup_consecutive(merged)


def _dedup_consecutive(steps: list[Step]) -> list[Step]:
    """Remove consecutive probe steps with identical normalised key."""
    out: list[Step] = []
    last_key: str | None = None
    for s in steps:
        k = normalize_key(s)
        if k == last_key and is_probe_step(s):
            continue
        out.append(s)
        last_key = k
    return out


# ── Metrics ────────────────────────────────────────────────────────


def candidate_metrics(original: list[Step], candidate: list[Step]) -> dict[str, Any]:
    cand_ids = {s.idx for s in candidate}
    return {
        "original_steps": len(original),
        "candidate_steps": len(candidate),
        "removed_steps": len(original) - len(candidate),
        "ok_original": sum(1 for s in original if s.status == "OK"),
        "ok_candidate": sum(1 for s in candidate if s.status == "OK"),
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
