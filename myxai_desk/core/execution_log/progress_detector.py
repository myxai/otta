"""Progress detector — determines whether a tool execution advanced the task state.

Each tool call gets a progress score:
  1  = advanced the state (URL changed, file created, command succeeded with new output)
  0  = did not advance (retry, same output, failed command)
 -1  = undetermined (tool type not recognised)

A ``state_sig`` (state signature) is a hash of observable state used to detect
whether consecutive calls of the same tool actually changed anything.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any


def detect_progress(
    tool_name: str,
    args: dict[str, Any] | None,
    result: Any,
    prev_state_sig: str = "",
) -> tuple[int, str]:
    """Return ``(progress, new_state_sig)`` for a single tool execution.

    Parameters
    ----------
    tool_name : name of the tool that was executed
    args : arguments passed to the tool
    result : raw result from tool execution
    prev_state_sig : state_sig from the previous step (same session)
    """
    args = args or {}
    result_str = str(result) if result is not None else ""

    if tool_name in ("web_fetch", "smart_fetch"):
        return _detect_fetch(args, result_str, prev_state_sig)
    if tool_name in ("write_file", "edit_file"):
        return _detect_write(args, result_str, prev_state_sig)
    if tool_name == "read_file":
        return _detect_read(args, result_str, prev_state_sig)
    if tool_name == "list_dir":
        return _detect_list_dir(args, result_str, prev_state_sig)
    if tool_name == "exec":
        return _detect_exec(args, result_str, prev_state_sig)
    if tool_name in ("web_search",):
        return _detect_search(args, result_str, prev_state_sig)
    if tool_name == "cron":
        return 1, _sig(result_str[:100])

    return -1, ""


# ── Per-tool detectors ─────────────────────────────────────────────

def _detect_fetch(args: dict, result: str, prev_sig: str) -> tuple[int, str]:
    url = args.get("url", "")
    sig = _sig(url)
    if sig != prev_sig and sig:
        return 1, sig
    return 0, sig


def _detect_write(args: dict, result: str, prev_sig: str) -> tuple[int, str]:
    path = args.get("path", args.get("file_path", ""))
    sig = _sig(path)
    if "error" in result.lower()[:100]:
        return 0, sig
    return 1, sig


def _detect_read(args: dict, result: str, prev_sig: str) -> tuple[int, str]:
    path = args.get("path", args.get("file_path", ""))
    sig = _sig(path + result[:200])
    if sig == prev_sig:
        return 0, sig
    return 1, sig


def _detect_list_dir(args: dict, result: str, prev_sig: str) -> tuple[int, str]:
    path = args.get("path", args.get("directory", ""))
    sig = _sig(path)
    if sig == prev_sig:
        return 0, sig
    return 1, sig


def _detect_exec(args: dict, result: str, prev_sig: str) -> tuple[int, str]:
    exit_code = _extract_exit_code(result)
    output_sig = _sig(result[:300])
    if exit_code == 0 and output_sig != prev_sig:
        return 1, output_sig
    if exit_code != 0:
        return 0, output_sig
    if output_sig == prev_sig:
        return 0, output_sig
    return 1, output_sig


def _detect_search(args: dict, result: str, prev_sig: str) -> tuple[int, str]:
    query = args.get("query", args.get("q", ""))
    sig = _sig(query)
    if sig != prev_sig:
        return 1, sig
    return 0, sig


# ── Helpers ────────────────────────────────────────────────────────

_EXIT_CODE_RE = re.compile(r"exit[_ ]?code[:\s=]+(\d+)", re.IGNORECASE)


def _extract_exit_code(result: str) -> int:
    m = _EXIT_CODE_RE.search(result[:300])
    if m:
        return int(m.group(1))
    if "error" in result.lower()[:100] or "traceback" in result.lower()[:200]:
        return 1
    return 0


def _sig(data: str) -> str:
    if not data:
        return ""
    return hashlib.md5(data.encode("utf-8", errors="replace")).hexdigest()[:12]
