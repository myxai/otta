"""Feature extraction — backward-compatible wrapper over the Persona Engine.

Existing code that calls ``extract_topics()`` or ``build_summary()`` keeps
working.  Internally we now delegate to the layer engines and persona store
instead of doing standalone rule-based extraction.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from myxai_desk.core.profile.events import EventStore
from myxai_desk.core.storage.paths import PROFILE_SUMMARY_FILE, ensure_dir

# ── Legacy digest paths (still used as a data source) ────────────

_APPS_DIR = Path.home() / ".nanobot" / "apps"
_DIGEST_DIR = _APPS_DIR / "daily_digest"
_DIGEST_REPORTS_DIR = _DIGEST_DIR / "reports"
_DIGEST_PROFILE_FILE = _DIGEST_DIR / "user_profile.json"


def _load_digest_interests(days: int = 7) -> dict | None:
    """Load LLM-analyzed interests from daily digest reports."""
    result: dict[str, list[str]] = {"work": [], "study": [], "life": []}
    found = False

    if _DIGEST_PROFILE_FILE.exists():
        try:
            profile = json.loads(_DIGEST_PROFILE_FILE.read_text(encoding="utf-8"))
            kw_counts: dict = profile.get("keyword_counts", {})
            if kw_counts:
                found = True
                sorted_kws = sorted(kw_counts.items(), key=lambda x: x[1], reverse=True)
                for kw, cnt in sorted_kws[:40]:
                    result["work"].append(kw)
        except Exception:
            pass

    if _DIGEST_REPORTS_DIR.exists():
        for f in sorted(_DIGEST_REPORTS_DIR.glob("*.json"), reverse=True)[:days]:
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                interests = d.get("interests")
                if not interests:
                    continue
                found = True
                for cat in ("work", "study", "life"):
                    for item in (interests.get(cat) or [])[:8]:
                        kw = item["keyword"] if isinstance(item, dict) else str(item)
                        if kw and kw not in result[cat]:
                            result[cat].append(kw)
            except Exception:
                pass

    if not found:
        return None
    for cat in result:
        result[cat] = result[cat][:15]
    return result


# ── Public: extract_topics (backward compatible) ─────────────────

def extract_topics(days: int = 7, store: EventStore | None = None) -> list[dict]:
    """Extract interest topics — now powered by the persona interest layer."""
    try:
        from myxai_desk.core.profile import persona_store
        from myxai_desk.core.profile.layers import interest_layer

        profile = persona_store.load()
        if profile.interests.topic_weight:
            topics = []
            for i, (topic, weight) in enumerate(
                sorted(profile.interests.topic_weight.items(),
                       key=lambda x: x[1], reverse=True)
            ):
                topics.append({
                    "topic": topic,
                    "category": "work",
                    "count": max(1, int(weight * 20)),
                    "score": weight,
                })
            return topics
    except Exception:
        pass

    digest = _load_digest_interests(days=days)
    if digest:
        topics = []
        for cat in ("work", "study", "life"):
            for i, kw in enumerate(digest[cat]):
                topics.append({
                    "topic": kw,
                    "category": cat,
                    "count": max(1, 10 - i),
                    "score": max(0.1, 1.0 - i * 0.1),
                })
        return topics

    return []


# ── Public: build_summary (backward compatible) ──────────────────

def build_summary(days: int = 30, store: EventStore | None = None) -> dict:
    """Build a profile summary — now delegates to persona engine when available."""
    try:
        from myxai_desk.core.profile import persona_store
        from myxai_desk.core.profile.prompt_builder import build_prompt

        profile = persona_store.load()
        if profile.overall_confidence() > 0.05:
            topics = extract_topics(days=days, store=store)
            return {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "source": "persona_engine",
                "persona_confidence": profile.overall_confidence(),
                "top_work_interests": [t["topic"] for t in topics if t["category"] == "work"][:10],
                "top_study_interests": [t["topic"] for t in topics if t["category"] == "study"][:10],
                "top_life_interests": [t["topic"] for t in topics if t["category"] == "life"][:5],
                "all_topics": topics[:30],
                "prompt_summary": build_prompt("general", profile=profile),
            }
    except Exception:
        pass

    store = store or EventStore()
    topics = extract_topics(days=min(days, 7), store=store)
    total_events = store.count()

    work_topics = [t for t in topics if t["category"] == "work"][:10]
    study_topics = [t for t in topics if t["category"] == "study"][:10]
    life_topics = [t for t in topics if t["category"] == "life"][:5]

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_events": total_events,
        "source": "legacy_fallback",
        "top_work_interests": [t["topic"] for t in work_topics],
        "top_study_interests": [t["topic"] for t in study_topics],
        "top_life_interests": [t["topic"] for t in life_topics],
        "all_topics": topics[:30],
    }

    ensure_dir(PROFILE_SUMMARY_FILE.parent)
    PROFILE_SUMMARY_FILE.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    return summary
