"""Capability layer engine — infer technical stack and skill levels.

Uses file extension frequency, browsing domains, and chat signals to
build a picture of the user's technical capabilities.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from myxai_desk.core.profile.persona_model import CapabilityLayer

_EXT_TO_LANG: dict[str, str] = {
    ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
    ".jsx": "React", ".tsx": "React", ".vue": "Vue",
    ".go": "Go", ".rs": "Rust", ".java": "Java", ".kt": "Kotlin",
    ".rb": "Ruby", ".php": "PHP", ".cs": "C#", ".cpp": "C++",
    ".c": "C", ".swift": "Swift", ".dart": "Dart",
    ".html": "HTML/CSS", ".css": "HTML/CSS", ".scss": "HTML/CSS",
    ".sql": "SQL", ".sh": "Shell", ".bat": "Shell", ".ps1": "PowerShell",
    ".yaml": "YAML/Config", ".yml": "YAML/Config", ".toml": "YAML/Config",
    ".json": "JSON", ".xml": "XML",
    ".md": "Documentation", ".rst": "Documentation",
    ".dockerfile": "Docker", ".tf": "Terraform",
}

_FRAMEWORK_SIGNALS: dict[str, list[str]] = {
    "Flask": ["flask"],
    "FastAPI": ["fastapi"],
    "Django": ["django"],
    "React": ["react", "jsx", "tsx"],
    "Vue": ["vue"],
    "WebView": ["webview", "pywebview"],
    "Docker": ["docker", "container", "dockerfile"],
    "Kubernetes": ["kubernetes", "k8s"],
}


def _infer_level(total_signals: int, unique_langs: int) -> str:
    if total_signals > 200 and unique_langs >= 4:
        return "高级"
    if total_signals > 50 and unique_langs >= 2:
        return "中高级"
    if total_signals > 10:
        return "中级"
    return "初级"


def update(
    events: list[dict],
    current: CapabilityLayer | None = None,
) -> CapabilityLayer:
    current = current or CapabilityLayer()

    lang_counter: Counter = Counter()
    framework_counter: Counter = Counter()
    arch_signals = 0
    product_signals = 0

    for e in events:
        et = e.get("event_type", "")
        if et == "file_touched":
            ext = e.get("file_extension", "")
            lang = _EXT_TO_LANG.get(ext)
            if lang:
                lang_counter[lang] += 1
        elif et == "browser_visited":
            kws = e.get("title_keywords") or []
            domain = e.get("domain", "")
            combined = " ".join(kws) + " " + domain
            lower = combined.lower()
            for fw, triggers in _FRAMEWORK_SIGNALS.items():
                if any(t in lower for t in triggers):
                    framework_counter[fw] += 1
            if any(kw in lower for kw in ("架构", "architecture", "system design", "设计模式")):
                arch_signals += 1
            if any(kw in lower for kw in ("产品", "product", "ux", "用户体验", "roadmap")):
                product_signals += 1
        elif et == "chat_message":
            session = (e.get("session") or "").lower()
            if any(kw in session for kw in ("架构", "设计", "architecture")):
                arch_signals += 1
            if any(kw in session for kw in ("产品", "用户", "product")):
                product_signals += 1

    top_langs = [lang for lang, _ in lang_counter.most_common(8)]
    top_frameworks = [fw for fw, _ in framework_counter.most_common(5)]
    coding_stack = top_langs[:5] + top_frameworks[:3]
    if not coding_stack:
        coding_stack = current.coding_stack

    total_signals = sum(lang_counter.values()) + sum(framework_counter.values())
    tech_level = _infer_level(total_signals, len(lang_counter))

    arch = "强" if arch_signals >= 5 else ("中" if arch_signals >= 2 else current.architecture_thinking)
    prod = "中高" if product_signals >= 5 else ("中" if product_signals >= 2 else current.product_design)

    return CapabilityLayer(
        technical_level=tech_level or current.technical_level,
        coding_stack=coding_stack,
        architecture_thinking=arch,
        product_design=prod,
        marketing_ops=current.marketing_ops or "待观察",
        confidence=min(1.0, total_signals / 30),
        signal_count=total_signals,
        last_updated=datetime.now(timezone.utc).isoformat(),
    )
