"""Slot extraction — two-layer design for Golden 2.0.

Layer 1 (rule-based): always runs, no network, extracts intent_label + typed
    slots from user text using regex patterns and keyword rules.

Layer 2 (LLM, optional): only invoked when rule-based confidence is low and
    network is available.  Uses a strict JSON-schema prompt.
"""

from __future__ import annotations

import os
import re
from typing import Any

from myxai_desk.core.golden.models import SlotResult

# ── Intent rules (ordered, first match wins) ─────────────────────

_INTENT_RULES: list[tuple[re.Pattern[str], str]] = [
    # File counting / stats
    (re.compile(
        r"统计|计数|count|多少个|文件数|数量",
        re.IGNORECASE,
    ), "count_files"),
    # Web search
    (re.compile(
        r"搜索|搜一下|查找.*(?:资料|信息|内容)|search|查询|google|百度|bing",
        re.IGNORECASE,
    ), "web_search"),
    # URL fetch / summarize
    (re.compile(
        r"https?://\S|抓取|获取.*(?:网页|页面)|fetch|摘要|简报|总结.*(?:网页|链接)",
        re.IGNORECASE,
    ), "web_fetch"),
    # File read
    (re.compile(
        r"读取|打开.*文件|read|cat\s|查看.*文件|显示.*内容",
        re.IGNORECASE,
    ), "read_file"),
    # File write / create
    (re.compile(
        r"写入|创建.*文件|write|新建|生成.*文件|保存.*到",
        re.IGNORECASE,
    ), "write_file"),
    # File edit
    (re.compile(
        r"编辑|修改.*文件|替换|edit|更新.*文件",
        re.IGNORECASE,
    ), "edit_file"),
    # List directory
    (re.compile(
        r"列出|目录|ls\s|list.*(?:dir|文件|目录)|文件列表",
        re.IGNORECASE,
    ), "list_dir"),
    # Shell / exec
    (re.compile(
        r"执行|运行|命令|exec|shell|cmd|pip\s|npm\s|git\s",
        re.IGNORECASE,
    ), "exec_cmd"),
    # Schedule / remind
    (re.compile(
        r"提醒|定时|闹钟|计划|cron|schedule|remind|每天|每周",
        re.IGNORECASE,
    ), "schedule"),
]

# ── Slot type patterns ───────────────────────────────────────────

_WINDOWS_PATH = re.compile(
    r'[A-Za-z]:[\\\/][\w\\\/.\-\u4e00-\u9fff\s]+'
)
_UNIX_PATH = re.compile(
    r'(?:~/|/(?:home|usr|tmp|var|opt|etc)/)[\w\/.\-]+'
)
_URL_PATTERN = re.compile(r'https?://\S+')
_NUMBER_PATTERN = re.compile(r'\b\d+(?:\.\d+)?\b')

# Slot name heuristics: which intent labels map to which slot types
_INTENT_SLOT_MAP: dict[str, list[tuple[str, str]]] = {
    "count_files": [("DIR", "path")],
    "read_file": [("FILE", "path")],
    "write_file": [("FILE", "path")],
    "edit_file": [("FILE", "path")],
    "list_dir": [("DIR", "path")],
    "web_search": [("QUERY", "string")],
    "web_fetch": [("URL", "url")],
    "exec_cmd": [("CMD", "string")],
    "schedule": [("TASK", "string")],
}


# ── Public API ───────────────────────────────────────────────────


def extract_slots(user_text: str) -> SlotResult:
    """Extract intent label and typed slots from user text (rule-based).

    Returns a SlotResult with intent_label, slots dict, and confidence.
    """
    text = (user_text or "").strip()
    if not text:
        return SlotResult()

    # Step 1: determine intent_label
    intent_label = _extract_intent(text)

    # Step 2: extract typed slot values
    slots = _extract_typed_slots(text, intent_label)

    # Step 3: if intent has no expected slots but we found paths/urls, use them
    if not slots:
        paths = _extract_paths(text)
        if paths:
            slots["PATH"] = paths[0]
        urls = _URL_PATTERN.findall(text)
        if urls:
            slots["URL"] = urls[0]

    # Confidence heuristic
    conf = 0.0
    if intent_label:
        conf += 0.5
    if slots:
        conf += 0.3
    expected = _INTENT_SLOT_MAP.get(intent_label, [])
    if expected and all(name in slots for name, _ in expected):
        conf += 0.2

    return SlotResult(
        intent_label=intent_label,
        slots=slots,
        confidence=min(conf, 1.0),
        extraction_mode="rule",
    )


# ── Internal helpers ─────────────────────────────────────────────


def _extract_intent(text: str) -> str:
    """Match the first intent rule against *text*."""
    for pattern, label in _INTENT_RULES:
        if pattern.search(text):
            return label
    return ""


def _extract_typed_slots(text: str, intent_label: str) -> dict[str, str]:
    """Extract slot values based on intent-specific expectations."""
    expected = _INTENT_SLOT_MAP.get(intent_label, [])
    slots: dict[str, str] = {}

    for slot_name, slot_type in expected:
        if slot_type == "path":
            paths = _extract_paths(text)
            if paths:
                slots[slot_name] = paths[0]
        elif slot_type == "url":
            urls = _URL_PATTERN.findall(text)
            if urls:
                slots[slot_name] = urls[0]
        elif slot_type == "number":
            nums = _NUMBER_PATTERN.findall(text)
            if nums:
                slots[slot_name] = nums[0]
        elif slot_type == "string":
            val = _extract_string_slot(text, intent_label, slot_name)
            if val:
                slots[slot_name] = val

    return slots


def _extract_paths(text: str) -> list[str]:
    """Extract file/directory paths from text."""
    paths: list[str] = []
    for m in _WINDOWS_PATH.finditer(text):
        paths.append(m.group().rstrip(" ."))
    for m in _UNIX_PATH.finditer(text):
        paths.append(m.group().rstrip(" ."))
    return paths


def _extract_string_slot(text: str, intent_label: str, slot_name: str) -> str:
    """Extract a free-text slot value by removing known keywords."""
    cleaned = text

    # Remove the intent trigger keywords
    for pattern, label in _INTENT_RULES:
        if label == intent_label:
            cleaned = pattern.sub("", cleaned)
            break

    # Remove paths and urls (they're handled by typed extraction)
    cleaned = _WINDOWS_PATH.sub("", cleaned)
    cleaned = _UNIX_PATH.sub("", cleaned)
    cleaned = _URL_PATTERN.sub("", cleaned)

    # Collapse whitespace and strip punctuation
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    cleaned = cleaned.strip("，。！？,.!? ")

    return cleaned if len(cleaned) >= 2 else ""


# ── Normalizers (used by store.compute_instance_key) ─────────────


def normalize_slot_value(value: str, slot_type: str, normalize_mode: str = "none") -> str:
    """Normalize a slot value for stable key computation."""
    if not value:
        return ""

    if slot_type == "path" or normalize_mode == "path_canonical":
        try:
            normed = os.path.abspath(value)
            normed = normed.replace("\\", "/")
            if os.name == "nt":
                normed = normed.lower()
            return normed
        except Exception:
            return value.replace("\\", "/").strip()

    if slot_type == "url":
        return value.strip().rstrip("/")

    if slot_type == "number":
        try:
            return str(float(value))
        except (ValueError, TypeError):
            return value.strip()

    if normalize_mode == "lowercase":
        return value.strip().lower()

    return value.strip()
