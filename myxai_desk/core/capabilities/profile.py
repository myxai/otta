"""Profile capability — unified API for Prompt Apps to access user context.

Provides topic summaries, project context, preference management, and
simplified persona engine access (stable + recent, prompt generation).
"""

from __future__ import annotations

import contextlib
import json
import uuid

from myxai_desk.core.profile.events import EventStore
from myxai_desk.core.profile.feature_extraction import (
    build_summary,
    extract_topics,
)
from myxai_desk.core.storage.paths import (
    PROFILE_PREFS_FILE,
    PROFILE_SUMMARY_FILE,
    ensure_dir,
)


def _new_action_id() -> str:
    return f"act_{uuid.uuid4().hex[:12]}"


class Profile:
    """Profile capability for Prompt Apps."""

    def __init__(self, *, store: EventStore | None = None):
        self._store = store or EventStore()

    # ── Legacy API (backward compatible) ─────────────────────────

    def get_summary(self) -> dict:
        """Return a pre-built profile summary (no raw URLs)."""
        if PROFILE_SUMMARY_FILE.exists():
            try:
                return json.loads(
                    PROFILE_SUMMARY_FILE.read_text(encoding="utf-8"),
                )
            except (json.JSONDecodeError, OSError):
                pass
        return build_summary(store=self._store)

    def get_topics(self, days: int = 30) -> list[dict]:
        """Return extracted interest topics."""
        return extract_topics(days=days, store=self._store)

    def get_project_context(self) -> dict:
        """Return current project/work context derived from recent activity."""
        topics = self.get_topics(days=7)
        work_topics = [t for t in topics if t["category"] == "work"]
        return {
            "active_projects": [t["topic"] for t in work_topics[:5]],
            "recent_technologies": [
                t["topic"] for t in work_topics if t["topic"] in _TECH_KEYWORDS
            ][:10],
        }

    def update_preferences(self, patch: dict) -> str:
        """Update user preferences.  Returns an ``ActionId``."""
        action_id = _new_action_id()
        ensure_dir(PROFILE_PREFS_FILE.parent)

        current = {}
        if PROFILE_PREFS_FILE.exists():
            with contextlib.suppress(json.JSONDecodeError, OSError):
                current = json.loads(
                    PROFILE_PREFS_FILE.read_text(encoding="utf-8"),
                )

        current.update(patch)
        PROFILE_PREFS_FILE.write_text(
            json.dumps(current, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return action_id

    def get_preferences(self) -> dict:
        """Return current user preferences."""
        if PROFILE_PREFS_FILE.exists():
            try:
                return json.loads(
                    PROFILE_PREFS_FILE.read_text(encoding="utf-8"),
                )
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def refresh_summary(self, days: int = 30) -> dict:
        """Force-rebuild the profile summary."""
        return build_summary(days=days, store=self._store)

    def get_collection_settings(self) -> dict:
        """Return current data collection settings."""
        prefs = self.get_preferences()
        defaults = {
            "browser_history": True,
            "chat_history": True,
            "file_history": False,
            "watch_paths": [],
            "analysis_days": 7,
            "persona_in_digest": False,
        }
        saved = prefs.get("collection", {})
        return {**defaults, **saved}

    def update_collection_settings(self, settings: dict) -> str:
        """Update data collection settings."""
        prefs = self.get_preferences()
        prefs["collection"] = settings
        return self.update_preferences(prefs)

    def export_all(self) -> dict:
        """Export all profile data for the user."""
        return {
            "summary": self.get_summary(),
            "topics": self.get_topics(),
            "preferences": self.get_preferences(),
            "persona": self.get_persona(),
            "events_count": self._store.count(),
        }

    def clear_all(self) -> str:
        """Clear all profile data.  Returns action_id."""
        action_id = _new_action_id()
        self._store.clear()
        for f in (PROFILE_SUMMARY_FILE, PROFILE_PREFS_FILE):
            if f.exists():
                f.rename(f.with_suffix(f.suffix + ".cleared"))
        try:
            from myxai_desk.core.profile import persona_store

            persona_store.delete_all()
        except Exception:
            pass
        return action_id

    # ── Persona Engine API (simplified) ──────────────────────────

    def get_persona(self) -> dict:
        """Return both stable + recent persona as a dict."""
        try:
            from myxai_desk.core.profile import persona_store

            stable = persona_store.load_stable()
            recent = persona_store.load_recent()
            return {
                "stable": stable.to_dict(),
                "recent": recent.to_dict(),
                "has_data": not stable.is_empty() or not recent.is_empty(),
            }
        except Exception:
            return {"stable": {}, "recent": {}, "has_data": False}

    def run_persona_update(
        self,
        *,
        model: str = "",
        api_key: str = "",
        api_base: str | None = None,
    ) -> dict:
        """Trigger a full persona update cycle."""
        try:
            from myxai_desk.core.profile.update_engine import run_full_update

            return run_full_update(
                model=model,
                api_key=api_key,
                api_base=api_base,
                store=self._store,
            )
        except Exception as e:
            return {"error": str(e)}

    def get_persona_prompt(self, task_context: str = "") -> str:
        """Generate persona-enhanced prompt for LLM injection."""
        try:
            from myxai_desk.core.profile.prompt_builder import build_prompt

            return build_prompt(task_context=task_context)
        except Exception:
            return ""

    def edit_persona_stable(self, patch: dict) -> dict:
        """Manually edit fields in the stable persona."""
        try:
            from myxai_desk.core.profile import persona_store

            stable = persona_store.load_stable()
            for key, value in patch.items():
                if hasattr(stable, key) and key not in ("updated_at",):
                    setattr(stable, key, value)
            from datetime import datetime, timezone

            stable.updated_at = datetime.now(timezone.utc).isoformat()
            persona_store.save_stable(stable)
            return {"status": "ok", "updated_fields": list(patch.keys())}
        except Exception as e:
            return {"error": str(e)}

    def edit_persona_recent(self, patch: dict) -> dict:
        """Manually edit fields in the recent snapshot."""
        try:
            from myxai_desk.core.profile import persona_store

            recent = persona_store.load_recent()
            for key, value in patch.items():
                if hasattr(recent, key) and key not in ("updated_at",):
                    setattr(recent, key, value)
            from datetime import datetime, timezone

            recent.updated_at = datetime.now(timezone.utc).isoformat()
            persona_store.save_recent(recent)
            return {"status": "ok", "updated_fields": list(patch.keys())}
        except Exception as e:
            return {"error": str(e)}


_TECH_KEYWORDS = {
    "python",
    "javascript",
    "typescript",
    "react",
    "vue",
    "angular",
    "node",
    "django",
    "flask",
    "fastapi",
    "docker",
    "kubernetes",
    "aws",
    "azure",
    "gcp",
    "git",
    "linux",
    "rust",
    "go",
    "java",
    "postgresql",
    "mongodb",
    "redis",
    "graphql",
    "rest",
    "api",
    "tensorflow",
    "pytorch",
    "llm",
    "openai",
    "langchain",
}
