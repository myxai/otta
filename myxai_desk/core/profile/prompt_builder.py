"""Prompt builder — task-aware persona compression for LLM injection.

Generates concise, high-density persona summaries (<=400 tokens) tailored
to the current task type.  The three-layer injection structure is:

    [Stable Persona]  +  [Current Focus Snapshot]  +  [Task Context]

Different task types emphasise different layers:
  - daily_briefing  -> goals + interest weights
  - product_design  -> capabilities + decision profile
  - security        -> risk preference + behavior patterns
  - general         -> identity + goals + output preference
"""

from __future__ import annotations

from myxai_desk.core.profile.persona_model import PersonaProfile
from myxai_desk.core.profile import persona_store


# ── Internal helpers ──────────────────────────────────────────────

def _stable_summary(p: PersonaProfile) -> str:
    parts: list[str] = []
    ident = p.identity
    if ident.role_type:
        line = f"- {ident.role_type}"
        if ident.industry_focus:
            line += f"，专注 {', '.join(ident.industry_focus[:3])}"
        parts.append(line)
    if ident.product_stage:
        parts.append(f"- 产品阶段：{ident.product_stage}")
    goals = p.goals
    if goals.long_term_goal:
        parts.append(f"- 长期目标：{goals.long_term_goal}")
    if goals.mid_term_goal:
        parts.append(f"- 中期目标：{goals.mid_term_goal}")
    return "\n".join(parts)


def _focus_snapshot(p: PersonaProfile) -> str:
    parts: list[str] = []
    if p.goals.current_focus:
        parts.append(f"- 当前重点：{', '.join(p.goals.current_focus[:4])}")
    top_interests = sorted(
        p.interests.topic_weight.items(), key=lambda x: x[1], reverse=True
    )[:5]
    if top_interests:
        items = [f"{k}({v:.0%})" for k, v in top_interests]
        parts.append(f"- 兴趣权重：{', '.join(items)}")
    rising = {k: v for k, v in p.interests.trend_shift.items() if v > 0}
    if rising:
        top_rising = sorted(rising.items(), key=lambda x: x[1], reverse=True)[:3]
        parts.append(f"- 上升趋势：{', '.join(k for k, _ in top_rising)}")
    return "\n".join(parts)


def _capability_block(p: PersonaProfile) -> str:
    parts: list[str] = []
    cap = p.capabilities
    if cap.technical_level:
        parts.append(f"- 技术水平：{cap.technical_level}")
    if cap.coding_stack:
        parts.append(f"- 技术栈：{', '.join(cap.coding_stack[:6])}")
    if cap.architecture_thinking:
        parts.append(f"- 架构思维：{cap.architecture_thinking}")
    if cap.product_design:
        parts.append(f"- 产品设计：{cap.product_design}")
    return "\n".join(parts)


def _decision_block(p: PersonaProfile) -> str:
    parts: list[str] = []
    dec = p.decision
    if dec.risk_preference:
        parts.append(f"- 风险偏好：{dec.risk_preference}")
    if dec.structure_preference:
        parts.append(f"- 输出偏好：{dec.structure_preference}")
    if dec.noise_tolerance:
        parts.append(f"- 噪声容忍：{dec.noise_tolerance}")
    if dec.execution_bias:
        parts.append(f"- 执行倾向：{dec.execution_bias}")
    if dec.dislike:
        parts.append(f"- 不喜欢：{', '.join(dec.dislike[:3])}")
    return "\n".join(parts)


def _behavior_block(p: PersonaProfile) -> str:
    parts: list[str] = []
    beh = p.behavior
    if beh.active_hours:
        parts.append(f"- 活跃时间：{beh.active_hours}")
    if beh.deep_work_pattern:
        parts.append(f"- 深度工作：{beh.deep_work_pattern}")
    if beh.project_focus_map:
        top = sorted(beh.project_focus_map.items(), key=lambda x: x[1], reverse=True)[:3]
        parts.append(f"- 项目专注：{', '.join(f'{k}({v:.0%})' for k, v in top)}")
    return "\n".join(parts)


# ── Task-type strategies ─────────────────────────────────────────

def _build_general(p: PersonaProfile) -> str:
    sections = [
        ("用户画像摘要", _stable_summary(p)),
        ("当前状态", _focus_snapshot(p)),
        ("能力结构", _capability_block(p)),
        ("决策风格", _decision_block(p)),
    ]
    return _format_sections(sections)


def _build_daily_briefing(p: PersonaProfile) -> str:
    sections = [
        ("用户画像摘要", _stable_summary(p)),
        ("当前目标与兴趣", _focus_snapshot(p)),
    ]
    return _format_sections(sections)


def _build_product_design(p: PersonaProfile) -> str:
    sections = [
        ("用户画像摘要", _stable_summary(p)),
        ("能力结构", _capability_block(p)),
        ("决策风格", _decision_block(p)),
    ]
    return _format_sections(sections)


def _build_security(p: PersonaProfile) -> str:
    sections = [
        ("用户画像摘要", _stable_summary(p)),
        ("决策风格", _decision_block(p)),
        ("行为模式", _behavior_block(p)),
    ]
    return _format_sections(sections)


def _build_minimal(p: PersonaProfile) -> str:
    """Ultra-compact version (<=150 tokens)."""
    parts: list[str] = []
    ident = p.identity
    if ident.role_type:
        line = ident.role_type
        if ident.industry_focus:
            line += f"，专注{'/'.join(ident.industry_focus[:2])}"
        parts.append(line + "。")
    if p.goals.long_term_goal:
        parts.append(f"目标：{p.goals.long_term_goal}。")
    if p.goals.current_focus:
        parts.append(f"当前重点：{', '.join(p.goals.current_focus[:3])}。")
    if p.capabilities.technical_level:
        parts.append(f"技术{p.capabilities.technical_level}，不需要基础教学。")
    dec = p.decision
    if dec.structure_preference:
        parts.append(f"偏{dec.structure_preference}、")
    if dec.noise_tolerance:
        parts[-1] = parts[-1].rstrip("、") + f"低噪声、可落地方案。" if dec.noise_tolerance == "低" else parts[-1]
    return "\n".join(parts)


def _format_sections(sections: list[tuple[str, str]]) -> str:
    blocks: list[str] = []
    for title, content in sections:
        if content.strip():
            blocks.append(f"{title}：\n{content}")
    return "\n\n".join(blocks)


# ── Public API ────────────────────────────────────────────────────

_STRATEGY_MAP = {
    "general": _build_general,
    "daily_briefing": _build_daily_briefing,
    "product_design": _build_product_design,
    "security": _build_security,
    "minimal": _build_minimal,
}

SUPPORTED_TASK_TYPES = list(_STRATEGY_MAP.keys())


def build_prompt(
    task_type: str = "general",
    *,
    profile: PersonaProfile | None = None,
    max_tokens: int = 400,
) -> str:
    """Build a task-aware persona prompt for LLM injection.

    *task_type* selects which layers to emphasise.  The output is a
    high-density Chinese text summary suitable for prepending to a
    system prompt.
    """
    if profile is None:
        profile = persona_store.load()

    if profile.overall_confidence() < 0.05:
        return ""

    builder = _STRATEGY_MAP.get(task_type, _build_general)
    return builder(profile)


def build_system_prompt_block(
    task_type: str = "general",
    *,
    profile: PersonaProfile | None = None,
    task_context: str = "",
) -> str:
    """Build the full three-layer system prompt injection block.

    Structure: [Stable Persona] + [Current Focus] + [Task Context]
    """
    if profile is None:
        profile = persona_store.load()

    persona_text = build_prompt(task_type, profile=profile)
    if not persona_text:
        return task_context

    parts = [persona_text]
    if task_context:
        parts.append(f"任务上下文：\n{task_context}")
    return "\n\n".join(parts)
