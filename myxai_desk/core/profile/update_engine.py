"""Simplified update engine — one-pass fusion analysis, two outputs.

Flow:
  1. Collect events from three sources (browser, chat, file)
  2. Aggregate into a structured summary
  3. Generate StablePersona + RecentSnapshot (LLM or rule-based)
  4. Save to persona_stable.json / persona_recent.json

Weight rule: file changes > chat signals > browser signals
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from myxai_desk.core.profile import persona_store
from myxai_desk.core.profile.events import EventStore
from myxai_desk.core.profile.persona_model import RecentSnapshot, StablePersona

# ── LLM Prompts ──────────────────────────────────────────────────

STABLE_PERSONA_PROMPT = """\
你是一个"用户画像压缩器"。将三类元数据压缩成一行高密度提示词。

严格按此格式输出（一行，用|分隔，不换行，不加标签）：
身份/领域 | 目标:关键词 | 能力:简评 | 偏好:风格关键词 | 约束:规则关键词

示例：
技术创业者/桌面AI | 目标:认知增强平台商业化 | 能力:全栈强,架构熟练 | 偏好:稳健+结构化+低噪声 | 约束:可落地/不泛泛/不基础教学

限制：整行不超过80字。只提取7天以上持续信号。不输出置信度。

以下是用户的三类元数据：

{data_block}"""

RECENT_SNAPSHOT_PROMPT = """\
你是一个"近期兴趣压缩器"。将最近7天数据压缩成两行高密度提示词。

严格按此格式输出（两行，不加标签）：
第一行 — 主题:名称(↑升温/=稳定),名称(↑/=)... | 项目:名称(阶段)
第二行 — 方向:关键词1/关键词2/关键词3/关键词4/关键词5

示例：
主题:桌面AI架构(↑),安全权限(↑),开源增长(=) | 项目:MyxAI(开发)
方向:Agent框架对比/安全分层设计/本地模型方案/开源增长案例/桌面AI产品调研

限制：两行合计不超过100字。只输出结果，不输出过程。

以下是最近7天的三类元数据：

{data_block}"""


# ── Data Collection ──────────────────────────────────────────────


def _collect_events(store: EventStore, days: int = 7) -> list[dict]:
    """Collect events in-memory only — no persistence to events.jsonl."""
    try:
        from myxai_desk.core.capabilities.profile import Profile

        settings = Profile().get_collection_settings()
    except Exception:
        settings = {}

    collect_days = min(days, settings.get("analysis_days", 7))
    events: list[dict] = []

    if settings.get("browser_history", True):
        try:
            from myxai_desk.core.profile.collectors.browser import collect_browser_events

            browser_events = collect_browser_events(hours=collect_days * 24)
            events.extend(browser_events)
        except Exception as e:
            print(f"[update_engine] Browser collect failed: {e}")

    if settings.get("chat_history", True):
        try:
            from myxai_desk.core.profile.collectors.chat import collect_chat_events

            chat_events = collect_chat_events(hours=collect_days * 24)
            events.extend(chat_events)
        except Exception as e:
            print(f"[update_engine] Chat collect failed: {e}")

    if settings.get("file_history") and settings.get("watch_paths"):
        try:
            from myxai_desk.core.profile.collectors.file_scanner import collect_file_events

            file_events = collect_file_events(settings["watch_paths"], days=collect_days)
            events.extend(file_events)
        except Exception as e:
            print(f"[update_engine] File scan failed: {e}")

    return events


# ── Aggregation ──────────────────────────────────────────────────


def _aggregate_events(events: list[dict]) -> dict[str, Any]:
    """Reduce raw events into a structured summary for prompt/rule input."""
    browser = [e for e in events if e.get("event_type") == "browser_visited"]
    chats = [e for e in events if e.get("event_type") == "chat_message"]
    files = [e for e in events if e.get("event_type") == "file_created"]

    # --- Browser: topic frequency ---
    topic_counter: Counter = Counter()
    category_counter: Counter = Counter()
    for e in browser:
        for kw in e.get("title_keywords", []):
            topic_counter[kw] += 1
        cat = e.get("category_tag", "")
        if cat:
            category_counter[cat] += 1

    # --- Chat: goal keywords + preferences ---
    goal_counter: Counter = Counter()
    output_prefs: Counter = Counter()
    depth_prefs: Counter = Counter()
    chat_topics: Counter = Counter()
    for e in chats:
        if e.get("role") != "user":
            continue
        for kw in e.get("goal_keywords") or []:
            goal_counter[kw] += 1
        op = e.get("output_preference", "")
        if op:
            output_prefs[op] += 1
        dp = e.get("depth_preference", "")
        if dp:
            depth_prefs[dp] += 1
        sess = e.get("session", "")
        if sess:
            chat_topics[sess] += 1

    # --- Files: newly created files by extension ---
    ext_counter: Counter = Counter()
    filename_keywords: Counter = Counter()
    for e in files:
        ext = e.get("extension", "")
        if ext and ext != "none":
            ext_counter[ext] += 1
        # Extract keywords from filename (simple word split)
        fname = e.get("filename", "")
        for word in fname.lower().replace("_", " ").replace("-", " ").split():
            if len(word) >= 3 and word.isalpha():
                filename_keywords[word] += 1

    return {
        "browser_topic_freq": topic_counter.most_common(20),
        "browser_categories": category_counter.most_common(10),
        "browser_count": len(browser),
        "chat_goals": goal_counter.most_common(10),
        "chat_output_pref": output_prefs.most_common(3),
        "chat_depth_pref": depth_prefs.most_common(3),
        "chat_topics": chat_topics.most_common(10),
        "chat_count": len(chats),
        "file_extensions": ext_counter.most_common(10),
        "file_name_keywords": filename_keywords.most_common(15),
        "file_count": len(files),
    }


def _build_data_block(agg: dict) -> str:
    """Format aggregated data into a text block for LLM prompts."""
    lines = []

    lines.append("## 1）浏览主题频率")
    if agg["browser_topic_freq"]:
        for kw, cnt in agg["browser_topic_freq"][:15]:
            lines.append(f"  - {kw}: {cnt}次")
    else:
        lines.append("  （无浏览数据）")

    lines.append("\n## 2）对话信号")
    if agg["chat_goals"]:
        lines.append("  目标关键词：")
        for kw, cnt in agg["chat_goals"][:8]:
            lines.append(f"  - {kw}: {cnt}次")
    if agg["chat_output_pref"]:
        top_pref = agg["chat_output_pref"][0][0]
        lines.append(f"  输出偏好：{top_pref}")
    if agg["chat_topics"]:
        lines.append("  对话主题：")
        for topic, cnt in agg["chat_topics"][:5]:
            lines.append(f"  - {topic}: {cnt}条消息")
    if not agg["chat_goals"] and not agg["chat_topics"]:
        lines.append("  （无对话数据）")

    lines.append("\n## 3）文件变更活跃度")
    if agg["file_extensions"]:
        exts = ", ".join(f"{ext}({cnt})" for ext, cnt in agg["file_extensions"][:8])
        lines.append(f"  新增文件类型：{exts}")
    if agg["file_name_keywords"]:
        keywords = ", ".join(f"{kw}({cnt})" for kw, cnt in agg["file_name_keywords"][:10])
        lines.append(f"  文件名关键词：{keywords}")
    if not agg["file_extensions"]:
        lines.append("  （无文件变更数据）")

    return "\n".join(lines)


# ── LLM-based Generation ────────────────────────────────────────


def _generate_with_llm(
    agg: dict,
    model: str,
    api_key: str,
    api_base: str | None = None,
    prev_stable: StablePersona | None = None,
    prev_recent: RecentSnapshot | None = None,
) -> tuple[StablePersona, RecentSnapshot]:
    from apps.llm_utils import llm_call, record_task_usage

    data_block = _build_data_block(agg)
    now_str = datetime.now(timezone.utc).isoformat()

    # Build context from previous persona
    prev_context = ""
    if prev_stable and not prev_stable.is_empty():
        prev_context += f"\n【上次稳定画像】\n{prev_stable.prompt_text}\n"
    if prev_recent and not prev_recent.is_empty():
        prev_context += f"\n【上次近期快照】\n{prev_recent.prompt_text}\n"

    if prev_context:
        prev_context = "\n" + prev_context + "\n请结合上次画像和新数据，更新画像内容。\n"

    # --- Stable Persona ---
    stable_prompt = STABLE_PERSONA_PROMPT.format(data_block=data_block) + prev_context
    stable_text = llm_call(
        messages=[{"role": "user", "content": stable_prompt}],
        model=model,
        api_key=api_key,
        api_base=api_base,
        temperature=0.3,
        max_tokens=500,
    )
    record_task_usage("persona", prompt_tokens=800, completion_tokens=300)

    stable = _parse_stable_output(stable_text)
    stable.prompt_text = stable_text.strip()
    stable.updated_at = now_str

    # --- Recent Snapshot ---
    recent_prompt = RECENT_SNAPSHOT_PROMPT.format(data_block=data_block)
    recent_text = llm_call(
        messages=[{"role": "user", "content": recent_prompt}],
        model=model,
        api_key=api_key,
        api_base=api_base,
        temperature=0.3,
        max_tokens=600,
    )
    record_task_usage("persona", prompt_tokens=800, completion_tokens=400)

    recent = _parse_recent_output(recent_text)
    recent.prompt_text = recent_text.strip()
    recent.updated_at = now_str

    return stable, recent


def _parse_stable_output(text: str) -> StablePersona:
    """Parse compressed single-line stable persona output."""
    persona = StablePersona()
    line = text.strip().splitlines()[0] if text.strip() else ""
    parts = [p.strip() for p in line.split("|")]

    if parts:
        persona.identity_role = parts[0]
    for p in parts[1:]:
        low = p.lower()
        if low.startswith("目标:") or low.startswith("目标："):
            persona.long_term_goals = [
                g.strip() for g in p.split(":", 1)[-1].split("：", 1)[-1].split(",")
            ]
        elif low.startswith("能力:") or low.startswith("能力："):
            persona.capability_assessment = p.split(":", 1)[-1].split("：", 1)[-1].strip()
        elif low.startswith("偏好:") or low.startswith("偏好："):
            persona.decision_preference = p.split(":", 1)[-1].split("：", 1)[-1].strip()
        elif low.startswith("约束:") or low.startswith("约束："):
            persona.output_constraints = [
                c.strip() for c in p.split(":", 1)[-1].split("：", 1)[-1].split("/")
            ]
    return persona


def _parse_recent_output(text: str) -> RecentSnapshot:
    """Parse compressed two-line recent snapshot output."""
    snapshot = RecentSnapshot()
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]

    for line in lines:
        if line.startswith("主题:") or line.startswith("主题："):
            topics_part = line
            if "|" in line:
                topics_part, proj_part = line.split("|", 1)
                proj_part = proj_part.strip()
                if "项目:" in proj_part or "项目：" in proj_part:
                    proj_str = proj_part.split(":", 1)[-1].split("：", 1)[-1].strip()
                    m = re.match(r"(.+?)\((.+?)\)", proj_str)
                    if m:
                        snapshot.active_project = {
                            "name": m.group(1).strip(),
                            "stage": m.group(2).strip(),
                        }

            topic_str = topics_part.split(":", 1)[-1].split("：", 1)[-1].strip()
            for t in topic_str.split(","):
                t = t.strip()
                m = re.match(r"(.+?)\((↑|↓|=|升温|稳定|下降)\)", t)
                if m:
                    trend_map = {"↑": "升温", "=": "稳定", "↓": "下降"}
                    snapshot.core_topics.append(
                        {
                            "topic": m.group(1).strip(),
                            "trend": trend_map.get(m.group(2), m.group(2)),
                        }
                    )
                elif t:
                    snapshot.core_topics.append({"topic": t, "trend": "稳定"})

        elif line.startswith("方向:") or line.startswith("方向："):
            rec_str = line.split(":", 1)[-1].split("：", 1)[-1].strip()
            snapshot.recommendations = [r.strip() for r in rec_str.split("/") if r.strip()]

    return snapshot


# ── Rule-based Fallback ──────────────────────────────────────────


def _generate_with_rules(agg: dict) -> tuple[StablePersona, RecentSnapshot]:
    """Produce persona outputs from aggregated data without LLM."""
    now_str = datetime.now(timezone.utc).isoformat()

    # ---- Stable Persona ----
    stable = StablePersona(updated_at=now_str)

    # Identity: infer from file extensions and filename keywords
    exts = {ext for ext, _ in agg["file_extensions"]}
    if exts & {".py", ".js", ".ts", ".go", ".rs", ".java"}:
        stable.identity_role = "技术开发者"
    elif exts & {".md", ".doc", ".docx", ".ppt"}:
        stable.identity_role = "内容/产品工作者"
    else:
        stable.identity_role = "知识工作者"

    # Infer project from filename keywords
    if agg["file_name_keywords"]:
        top_keywords = [kw for kw, _ in agg["file_name_keywords"][:3]]
        stable.identity_role += f"，活跃领域：{'/'.join(top_keywords)}"

    # Goals from chat
    if agg["chat_goals"]:
        stable.long_term_goals = [kw for kw, cnt in agg["chat_goals"][:2] if cnt >= 2]

    # Capability from tech stack
    tech_exts = exts & {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java", ".cpp"}
    if tech_exts:
        stable.capability_assessment = f"技术能力较强，常用 {', '.join(sorted(tech_exts)[:5])}"
    else:
        stable.capability_assessment = "技术栈待观察"

    # Decision preference from chat signals
    pref_parts = []
    if agg["chat_output_pref"]:
        pref_parts.append(f"偏好{agg['chat_output_pref'][0][0]}输出")
    if agg["chat_depth_pref"]:
        pref_parts.append(f"深度偏好：{agg['chat_depth_pref'][0][0]}")
    stable.decision_preference = "，".join(pref_parts) if pref_parts else "偏好结构化输出"

    # Output constraints
    constraints = []
    if agg["chat_output_pref"] and agg["chat_output_pref"][0][0] == "structured":
        constraints.append("优先使用结构化输出")
    constraints.append("避免泛泛讨论，提供可落地建议")
    if tech_exts:
        constraints.append("不需要基础教学")
    stable.output_constraints = constraints

    # Build compressed prompt text (single line, pipe-separated)
    segments = [stable.identity_role or "知识工作者"]
    if stable.long_term_goals:
        segments.append("目标:" + ",".join(stable.long_term_goals))
    if stable.capability_assessment:
        segments.append("能力:" + stable.capability_assessment)
    if stable.decision_preference:
        segments.append("偏好:" + stable.decision_preference)
    if stable.output_constraints:
        segments.append("约束:" + "/".join(stable.output_constraints))
    stable.prompt_text = " | ".join(segments)

    # ---- Recent Snapshot ----
    recent = RecentSnapshot(updated_at=now_str)

    # Core topics: merge browser + chat topics + filename keywords
    # Weight: file keywords > chat > browser
    merged: Counter = Counter()
    for kw, cnt in agg["browser_topic_freq"]:
        merged[kw] += cnt * 1
    for kw, cnt in agg["chat_goals"]:
        merged[kw] += cnt * 3
    for topic, cnt in agg["chat_topics"]:
        for word in topic.split()[:3]:
            if len(word) >= 2:
                merged[word] += cnt * 2
    for kw, cnt in agg["file_name_keywords"]:
        merged[kw] += cnt * 5

    top_topics = merged.most_common(3)
    for kw, score in top_topics:
        recent.core_topics.append(
            {
                "topic": kw,
                "trend": "升温" if score > 5 else "稳定",
                "evidence": f"加权得分 {score}",
            }
        )

    # Active project from file keywords
    if agg["file_name_keywords"]:
        top_kw, top_cnt = agg["file_name_keywords"][0]
        if top_cnt >= 3:
            stage = "开发"
            if agg["file_count"] < 5:
                stage = "探索"
            elif agg["file_count"] > 20:
                stage = "优化"
            recent.active_project = {"name": top_kw, "stage": stage}

    # Recommendations from top topics
    for kw, _ in top_topics:
        recent.recommendations.append(f"关于「{kw}」的最新实践/工具")
    if recent.active_project.get("name"):
        recent.recommendations.append(f"与 {recent.active_project['name']} 同类项目的架构对比")
    recent.recommendations.append("近期热门技术动态")
    recent.recommendations = recent.recommendations[:5]

    # Build compressed prompt text (two lines max)
    line1_parts = []
    if recent.core_topics:
        trend_map = {"升温": "↑", "稳定": "=", "下降": "↓"}
        topics_str = ",".join(
            f"{t['topic']}({trend_map.get(t.get('trend', '稳定'), '=')})"
            for t in recent.core_topics
        )
        line1_parts.append("主题:" + topics_str)
    if recent.active_project.get("name"):
        proj = recent.active_project
        line1_parts.append(f"项目:{proj['name']}({proj.get('stage', '开发')})")
    line1 = " | ".join(line1_parts) if line1_parts else ""

    line2 = ""
    if recent.recommendations:
        line2 = "方向:" + "/".join(recent.recommendations[:5])

    recent.prompt_text = "\n".join(filter(None, [line1, line2]))

    return stable, recent


# ── Public API ───────────────────────────────────────────────────


def run_full_update(
    *,
    model: str = "",
    api_key: str = "",
    api_base: str | None = None,
    store: EventStore | None = None,
) -> dict[str, Any]:
    """Run a full persona update: collect → aggregate → generate → save.

    If *model* and *api_key* are provided, uses LLM for generation;
    otherwise falls back to rule-based extraction.
    """
    store = store or EventStore()
    store.clear()
    events = _collect_events(store)

    if not events:
        return {"status": "no_events", "message": "没有收集到任何数据"}

    agg = _aggregate_events(events)
    use_llm = bool(model and api_key)

    # Load previous persona for context
    prev_stable = persona_store.load_stable()
    prev_recent = persona_store.load_recent()

    try:
        if use_llm:
            stable, recent = _generate_with_llm(
                agg,
                model,
                api_key,
                api_base,
                prev_stable=prev_stable,
                prev_recent=prev_recent,
            )
        else:
            stable, recent = _generate_with_rules(agg)
    except Exception as e:
        print(f"[update_engine] LLM generation failed, falling back to rules: {e}")
        stable, recent = _generate_with_rules(agg)

    persona_store.save_stable(stable)
    persona_store.save_recent(recent)

    return {
        "status": "ok",
        "method": "llm" if use_llm else "rules",
        "total_events": len(events),
        "event_breakdown": {
            "browser": agg["browser_count"],
            "chat": agg["chat_count"],
            "file": agg["file_count"],
        },
        "stable_preview": stable.identity_role,
        "recent_topics": [t.get("topic", "") for t in recent.core_topics],
    }
