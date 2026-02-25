"""Identity layer engine — infer stable user identity from metadata.

Examines browsing patterns, file extensions, and chat signals to infer
role_type, industry_focus, product_stage, and work_mode.

This layer only updates weekly and requires confidence > 0.7.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from myxai_desk.core.profile.persona_model import IdentityLayer

# ── Industry inference rules ─────────────────────────────────────

_INDUSTRY_SIGNALS: dict[str, list[str]] = {
    "AI Agent": ["agent", "llm", "gpt", "openai", "langchain", "大模型", "ai"],
    "Web开发": ["react", "vue", "angular", "frontend", "backend", "前端", "后端"],
    "移动开发": ["android", "ios", "flutter", "swift", "kotlin", "移动"],
    "数据科学": ["pandas", "numpy", "jupyter", "数据分析", "machine learning"],
    "DevOps": ["docker", "kubernetes", "ci/cd", "部署", "运维", "pipeline"],
    "安全": ["security", "安全", "加密", "渗透", "vulnerability"],
    "开源软件": ["github", "开源", "open source", "contributor", "pr"],
    "桌面AI": ["desktop", "桌面", "electron", "webview", "pywebview"],
}

_ROLE_SIGNALS: dict[str, list[str]] = {
    "开发者": [".py", ".js", ".ts", ".go", ".rs", ".java", "code", "开发", "debug"],
    "产品经理": ["prd", "需求", "用户体验", "product", "feature", "roadmap"],
    "创业者": ["商业化", "融资", "增长", "创业", "startup", "mvp", "growth"],
    "研究员": ["paper", "论文", "研究", "arxiv", "research", "实验"],
    "设计师": ["figma", "sketch", "design", "设计", "UI", "UX", "原型"],
}

_STAGE_SIGNALS: dict[str, list[str]] = {
    "探索期": ["调研", "学习", "了解", "tutorial", "入门", "概念"],
    "早期快速迭代": ["mvp", "原型", "迭代", "prototype", "快速", "验证"],
    "增长期": ["增长", "用户", "推广", "marketing", "growth", "scale"],
    "成熟期": ["优化", "重构", "稳定", "性能", "monitoring", "maintenance"],
}


def _count_signals(keywords: list[str], signal_map: dict[str, list[str]]) -> Counter:
    counter: Counter = Counter()
    lower_kws = [k.lower() for k in keywords]
    for label, triggers in signal_map.items():
        for trigger in triggers:
            for kw in lower_kws:
                if trigger in kw:
                    counter[label] += 1
    return counter


def update(
    events: list[dict],
    current: IdentityLayer | None = None,
) -> IdentityLayer:
    current = current or IdentityLayer()

    all_keywords: list[str] = []
    all_extensions: list[str] = []

    for e in events:
        et = e.get("event_type", "")
        if et == "browser_visited":
            all_keywords.extend(e.get("title_keywords") or [])
            all_keywords.append(e.get("category_tag", ""))
            all_keywords.append(e.get("domain", ""))
        elif et == "chat_message":
            all_keywords.extend(e.get("goal_keywords") or [])
            all_keywords.append(e.get("session", ""))
        elif et == "file_touched":
            all_extensions.append(e.get("file_extension", ""))
            all_keywords.append(e.get("project_prefix", ""))
        elif et == "search_performed":
            all_keywords.extend(e.get("query", "").split())

    all_keywords = [k for k in all_keywords if k]
    combined = all_keywords + all_extensions

    industry_counts = _count_signals(combined, _INDUSTRY_SIGNALS)
    role_counts = _count_signals(combined, _ROLE_SIGNALS)
    stage_counts = _count_signals(combined, _STAGE_SIGNALS)

    industry_focus = [label for label, _ in industry_counts.most_common(3)] or current.industry_focus
    role_type = role_counts.most_common(1)[0][0] if role_counts else current.role_type
    product_stage = stage_counts.most_common(1)[0][0] if stage_counts else current.product_stage

    work_modes: Counter = Counter()
    for e in events:
        if e.get("event_type") == "chat_message" and e.get("role") == "user":
            work_modes["self_driven"] += 1
    work_mode = "高度自主驱动" if work_modes.get("self_driven", 0) > 5 else current.work_mode

    signal_count = len(combined)
    return IdentityLayer(
        role_type=role_type,
        industry_focus=industry_focus,
        product_stage=product_stage,
        work_mode=work_mode,
        primary_device=current.primary_device or "Windows桌面",
        confidence=min(1.0, signal_count / 50),
        signal_count=signal_count,
        last_updated=datetime.now(timezone.utc).isoformat(),
    )
