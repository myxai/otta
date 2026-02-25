"""Prompt builder — compressed persona injection for system prompts.

Output format (~50-80 tokens total):

    [P] 身份/领域 | 目标:xxx | 能力:xxx | 偏好:xxx | 约束:xxx
    [R] 主题:A(↑),B(=) | 项目:X(开发)
    [R] 方向:关键词1/关键词2/关键词3

[P] = stable persona, [R] = recent snapshot.
"""

from __future__ import annotations

from myxai_desk.core.profile import persona_store


def build_prompt(*, task_context: str = "") -> str:
    """Build a compressed persona block for system prompt injection.

    Returns empty string if no persona data exists.
    """
    stable = persona_store.load_stable()
    recent = persona_store.load_recent()

    if stable.is_empty() and recent.is_empty():
        return ""

    lines: list[str] = []
    if not stable.is_empty() and stable.prompt_text:
        lines.append(f"[P] {stable.prompt_text}")
    if not recent.is_empty() and recent.prompt_text:
        for rline in recent.prompt_text.splitlines():
            if rline.strip():
                lines.append(f"[R] {rline.strip()}")
    if task_context:
        lines.append(f"[C] {task_context}")

    return "\n".join(lines)


def get_stable_prompt() -> str:
    """Return only the compressed stable persona line."""
    stable = persona_store.load_stable()
    if stable.is_empty() or not stable.prompt_text:
        return ""
    return f"[P] {stable.prompt_text}"


def get_recent_prompt() -> str:
    """Return only the compressed recent snapshot lines."""
    recent = persona_store.load_recent()
    if recent.is_empty() or not recent.prompt_text:
        return ""
    return "\n".join(
        f"[R] {line.strip()}"
        for line in recent.prompt_text.splitlines()
        if line.strip()
    )
