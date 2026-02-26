"""Unified path management for all ~/.nanobot/ directories.

Every module should import paths from here instead of constructing
``Path.home() / ".nanobot" / ...`` on its own.
"""

from pathlib import Path

NANOBOT_HOME: Path = Path.home() / ".nanobot"

# ── Core data directories ──────────────────────────────────────────

TRASH_DIR: Path = NANOBOT_HOME / "trash"
HISTORY_DIR: Path = NANOBOT_HOME / "desktop_history"
SESSIONS_FILE: Path = HISTORY_DIR / "sessions.json"
USAGE_DIR: Path = NANOBOT_HOME / "usage"
CASES_DIR: Path = NANOBOT_HOME / "desktop_cases"

# ── Audit ──────────────────────────────────────────────────────────

AUDIT_DIR: Path = NANOBOT_HOME / "audit"
AUDIT_LEDGER_FILE: Path = AUDIT_DIR / "ledger.jsonl"

# ── Apps ───────────────────────────────────────────────────────────

APPS_DIR: Path = NANOBOT_HOME / "apps"
APPS_REGISTRY_FILE: Path = APPS_DIR / "registry.json"
APPS_PREFS_FILE: Path = APPS_DIR / "prefs.json"

CUSTOM_APPS_DIR: Path = APPS_DIR / "custom"
DAILY_DIGEST_DIR: Path = APPS_DIR / "daily_digest"
EMAIL_SUMMARY_DIR: Path = APPS_DIR / "email_summary"

# ── Profile ────────────────────────────────────────────────────────

PROFILE_DIR: Path = NANOBOT_HOME / "profile"
PROFILE_EVENTS_FILE: Path = PROFILE_DIR / "events.jsonl"
PROFILE_SUMMARY_FILE: Path = PROFILE_DIR / "summary.json"
PROFILE_PREFS_FILE: Path = PROFILE_DIR / "preferences.json"

# ── Persona Engine (simplified: two-file output) ─────────────────

PERSONA_STABLE_FILE: Path = PROFILE_DIR / "persona_stable.json"
PERSONA_RECENT_FILE: Path = PROFILE_DIR / "persona_recent.json"

# ── Security / Policy ──────────────────────────────────────────────

POLICY_DIR: Path = NANOBOT_HOME / "policy"
SECURITY_MODE_FILE: Path = POLICY_DIR / "mode.json"

# ── Scheduler ─────────────────────────────────────────────────────

SCHEDULER_DIR: Path = NANOBOT_HOME / "scheduler"

# ── Desk (desktop app preferences) ────────────────────────────────

DESK_SETTINGS_FILE: Path = NANOBOT_HOME / "desk_settings.json"

# ── Token & search usage ──────────────────────────────────────────

TOKEN_USAGE_FILE: Path = USAGE_DIR / "token_usage.json"
SEARCH_USAGE_FILE: Path = USAGE_DIR / "search_usage.json"


def ensure_dir(path: Path) -> Path:
    """Create *path* (and parents) if it does not exist, then return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path
