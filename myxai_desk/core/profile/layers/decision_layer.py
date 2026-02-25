"""Decision layer engine — model the user's decision-making style.

Analyses conversation patterns to infer risk_preference, structure_preference,
noise_tolerance, and execution_bias.  Updated monthly.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from myxai_desk.core.profile.persona_model import DecisionLayer


_RISK_HIGH = {"大胆", "激进", "冒险", "尝试", "experimental", "risky", "bold"}
_RISK_LOW = {"稳健", "保守", "安全", "稳定", "safe", "conservative", "careful"}

_NOISE_LOW_MARKERS = {"不要废话", "直接", "简洁", "别啰嗦", "skip", "no fluff", "concise",
                      "别解释基础", "不需要科普"}
_NOISE_HIGH_MARKERS = {"详细", "展开", "背景", "上下文", "context", "background", "elaborate"}

_EXEC_FAST = {"快速", "验证", "mvp", "原型", "先做", "quick", "prototype", "ship"}
_EXEC_THOROUGH = {"彻底", "完善", "完整", "全面", "comprehensive", "thorough", "robust"}


def update(
    events: list[dict],
    current: DecisionLayer | None = None,
) -> DecisionLayer:
    current = current or DecisionLayer()

    structure_counter: Counter = Counter()
    risk_counter: Counter = Counter()
    noise_counter: Counter = Counter()
    exec_counter: Counter = Counter()
    dislike_counter: Counter = Counter()

    user_events = [e for e in events
                   if e.get("event_type") == "chat_message" and e.get("role") == "user"]

    for e in user_events:
        op = e.get("output_preference", "")
        if op:
            structure_counter[op] += 1

        session = (e.get("session") or "").lower()
        digest = (e.get("text_digest") or "").lower()
        combined = session + " " + digest

        for kw in _RISK_HIGH:
            if kw in combined:
                risk_counter["aggressive"] += 1
        for kw in _RISK_LOW:
            if kw in combined:
                risk_counter["conservative"] += 1

        for kw in _NOISE_LOW_MARKERS:
            if kw in combined:
                noise_counter["low"] += 1
        for kw in _NOISE_HIGH_MARKERS:
            if kw in combined:
                noise_counter["high"] += 1

        for kw in _EXEC_FAST:
            if kw in combined:
                exec_counter["fast_validation"] += 1
        for kw in _EXEC_THOROUGH:
            if kw in combined:
                exec_counter["thorough"] += 1

    struct_pref = structure_counter.most_common(1)[0][0] if structure_counter else current.structure_preference
    struct_label_map = {
        "structured": "强结构化输出",
        "code_first": "代码优先",
        "concise": "简洁优先",
    }
    struct_pref = struct_label_map.get(struct_pref, struct_pref)

    risk_top = risk_counter.most_common(1)
    if risk_top:
        risk_label = {"aggressive": "偏激进", "conservative": "中等偏稳健"}
        risk_pref = risk_label.get(risk_top[0][0], "中等")
    else:
        risk_pref = current.risk_preference or "中等"

    noise_top = noise_counter.most_common(1)
    noise_tol = "低" if (noise_top and noise_top[0][0] == "low") else (
        "高" if (noise_top and noise_top[0][0] == "high") else (current.noise_tolerance or "中"))

    exec_top = exec_counter.most_common(1)
    exec_label_map = {"fast_validation": "快速验证优先", "thorough": "彻底完善优先"}
    exec_bias = exec_label_map.get(exec_top[0][0], current.execution_bias) if exec_top else (
        current.execution_bias or "")

    signal_count = len(user_events)
    return DecisionLayer(
        risk_preference=risk_pref,
        structure_preference=struct_pref,
        noise_tolerance=noise_tol,
        execution_bias=exec_bias,
        dislike=current.dislike or [],
        confidence=min(1.0, signal_count / 30),
        signal_count=signal_count,
        last_updated=datetime.now(timezone.utc).isoformat(),
    )
