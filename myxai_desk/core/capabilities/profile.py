"""Profile capability — unified API for Prompt Apps to access user context.

Provides topic summaries, project context, preference management, and
full persona engine access (CRUD, versioning, prompt generation).
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from myxai_desk.core.storage.paths import (
    PROFILE_SUMMARY_FILE, PROFILE_PREFS_FILE, ensure_dir,
)
from myxai_desk.core.profile.events import EventStore
from myxai_desk.core.profile.feature_extraction import (
    build_summary, extract_topics,
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
                t["topic"] for t in work_topics
                if t["topic"] in _TECH_KEYWORDS
            ][:10],
        }

    def update_preferences(self, patch: dict) -> str:
        """Update user preferences.  Returns an ``ActionId``."""
        action_id = _new_action_id()
        ensure_dir(PROFILE_PREFS_FILE.parent)

        current = {}
        if PROFILE_PREFS_FILE.exists():
            try:
                current = json.loads(
                    PROFILE_PREFS_FILE.read_text(encoding="utf-8"),
                )
            except (json.JSONDecodeError, OSError):
                pass

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
        return prefs.get("collection", {
            "browser_history": True,
            "chat_history": True,
            "file_history": False,
            "watch_paths": [],
            "retention_days": 90,
        })

    def update_collection_settings(self, settings: dict) -> str:
        """Update data collection settings."""
        prefs = self.get_preferences()
        prefs["collection"] = settings
        return self.update_preferences(prefs)

    def export_all(self) -> dict:
        """Export all profile data for the user."""
        persona = self.get_persona()
        return {
            "summary": self.get_summary(),
            "topics": self.get_topics(),
            "preferences": self.get_preferences(),
            "persona": persona,
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

    # ── Persona Engine API ───────────────────────────────────────

    def get_persona(self) -> dict:
        """Return the full 6-layer persona profile as a dict."""
        try:
            from myxai_desk.core.profile import persona_store
            return persona_store.load().to_dict()
        except Exception:
            return {}

    def get_persona_layer(self, layer_name: str) -> dict:
        """Return a single persona layer as a dict."""
        try:
            from myxai_desk.core.profile import persona_store
            from dataclasses import asdict
            profile = persona_store.load()
            layer = profile.get_layer(layer_name)
            return asdict(layer)
        except Exception as e:
            return {"error": str(e)}

    def update_persona_layer(self, layer_name: str, patch: dict) -> dict:
        """Manually update fields in a persona layer."""
        try:
            from myxai_desk.core.profile.update_engine import manual_update_layer
            return manual_update_layer(layer_name, patch)
        except Exception as e:
            return {"error": str(e)}

    def run_persona_update(self, *, force: bool = False) -> dict:
        """Trigger a full persona engine update cycle."""
        try:
            from myxai_desk.core.profile.update_engine import run_full_update
            return run_full_update(force=force, store=self._store)
        except Exception as e:
            return {"error": str(e)}

    def get_persona_versions(self) -> list[dict]:
        """List all stored persona versions."""
        try:
            from myxai_desk.core.profile import persona_store
            return persona_store.list_versions()
        except Exception:
            return []

    def rollback_persona(self, version: int) -> dict:
        """Rollback persona to a specific version."""
        try:
            from myxai_desk.core.profile import persona_store
            profile = persona_store.rollback(version)
            return {"success": True, "version": version, "confidence": profile.overall_confidence()}
        except FileNotFoundError:
            return {"error": f"Version {version} not found"}
        except Exception as e:
            return {"error": str(e)}

    def get_persona_prompt(self, task_type: str = "general") -> str:
        """Generate a task-aware persona prompt for LLM injection."""
        try:
            from myxai_desk.core.profile.prompt_builder import build_prompt
            return build_prompt(task_type)
        except Exception:
            return ""

    def get_persona_audit(self, n: int = 50) -> list[dict]:
        """Return recent persona audit log entries."""
        try:
            from myxai_desk.core.profile import persona_audit
            return persona_audit.recent(n=n)
        except Exception:
            return []


_TECH_KEYWORDS = {
    "python", "javascript", "typescript", "react", "vue", "angular",
    "node", "django", "flask", "fastapi", "docker", "kubernetes",
    "aws", "azure", "gcp", "git", "linux", "rust", "go", "java",
    "postgresql", "mongodb", "redis", "graphql", "rest", "api",
    "tensorflow", "pytorch", "llm", "openai", "langchain",
}
