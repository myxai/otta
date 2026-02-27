"""Apps 共享工具模块 — 注册表、偏好、目录常量.

从 app.py 中抽取，供 apps_routes / apps_digest_routes /
apps_email_routes / apps_custom_routes 共用。
"""

import json
import logging
import threading
from pathlib import Path


# ── 路径常量 ──────────────────────────────────────────────────────

APPS_DIR = Path.home() / ".nanobot" / "apps"
APPS_REGISTRY = APPS_DIR / "registry.json"
APPS_PREFS = APPS_DIR / "prefs.json"

log = logging.getLogger("myxai.web.apps_helpers")


# ── 注册表 I/O ────────────────────────────────────────────────────

def load_apps_registry() -> dict:
    APPS_DIR.mkdir(parents=True, exist_ok=True)
    if APPS_REGISTRY.exists():
        try:
            data = json.loads(APPS_REGISTRY.read_text(encoding="utf-8"))
        except Exception:
            log.warning("Failed to load apps registry (invalid JSON)", exc_info=True)
            return {}
        if "healthcheck" in data and "execution_radar" not in data:
            data["execution_radar"] = data.pop("healthcheck")
            save_apps_registry(data)
            log.info("Migrated registry key 'healthcheck' → 'execution_radar'")
        return data
    return {}


def save_apps_registry(data: dict):
    APPS_DIR.mkdir(parents=True, exist_ok=True)
    APPS_REGISTRY.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── 偏好 I/O ──────────────────────────────────────────────────────

def load_apps_prefs() -> dict:
    if APPS_PREFS.exists():
        try:
            data = json.loads(APPS_PREFS.read_text(encoding="utf-8"))
        except Exception:
            log.warning("Failed to load apps prefs (invalid JSON)", exc_info=True)
            return {}
        if "healthcheck" in data and "execution_radar" not in data:
            data["execution_radar"] = data.pop("healthcheck")
            save_apps_prefs(data)
        return data
    return {}


def save_apps_prefs(data: dict):
    APPS_DIR.mkdir(parents=True, exist_ok=True)
    APPS_PREFS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def inc_run_count(app_id: str):
    prefs = load_apps_prefs()
    p = prefs.setdefault(app_id, {})
    p["run_count"] = p.get("run_count", 0) + 1
    save_apps_prefs(prefs)


# ── 翻译辅助 ──────────────────────────────────────────────────────

def _t(key: str, **kwargs) -> str:
    try:
        from myxai_desk.core.i18n import get_translator
        return get_translator().t(key, **kwargs)
    except Exception:
        log.debug("Translation failed for key %s, returning key", key, exc_info=True)
        return key


# ── 内置应用目录 ──────────────────────────────────────────────────

APP_CATALOG = {
    "daily_digest": {
        "id": "daily_digest",
        "name": _t("app.daily_digest.name"),
        "name_en": "Daily Briefing",
        "icon": "🎯",
        "description": _t("app.daily_digest.desc"),
        "description_en": "Your personal curator — daily picks based on your interests, with deep-dive exploration",
        "version": "2.0.0",
        "author": "nanobot",
        "category": "productivity",
        "min_mode": "Observer",
    },
    "email_summary": {
        "id": "email_summary",
        "name": _t("app.email_summary.name"),
        "name_en": "Email Briefing",
        "icon": "📧",
        "description": _t("app.email_summary.desc"),
        "description_en": "Connect your inbox, AI categorises and summarises into a daily briefing",
        "version": "1.0.0",
        "author": "nanobot",
        "category": "productivity",
        "min_mode": "Assistant",
    },
    "execution_radar": {
        "id": "execution_radar",
        "name": _t("app.execution_radar.name"),
        "name_en": "Execution Radar",
        "icon": "📡",
        "description": _t("app.execution_radar.desc"),
        "description_en": "Daily execution quality analytics — hit rates, error trends, tool diagnostics",
        "version": "1.0.0",
        "author": "nanobot",
        "category": "analytics",
        "min_mode": "Observer",
    },
    "intent_engine": {
        "id": "intent_engine",
        "name": _t("app.intent_engine.name"),
        "name_en": "Intent Engine",
        "icon": "🧠",
        "description": _t("app.intent_engine.desc"),
        "description_en": "Intent classification, tool routing, case retrieval, plan reuse — closed-loop execution intelligence",
        "version": "1.0.0",
        "author": "nanobot",
        "category": "analytics",
        "min_mode": "Observer",
    },
}

DEFAULT_DIGEST_CONFIG = {
    "browser": "auto",
    "history_hours": 24,
    "schedule_time": "22:00",
    "push_notification": True,
    "push_email": "",
}

DEFAULT_EXECUTION_RADAR_CONFIG = {
    "schedule_time": "02:00",
}

DEFAULT_INTENT_ENGINE_CONFIG = {
    "routing_enabled": True,
    "case_retrieval_enabled": False,
    "plan_reuse_enabled": False,
    "schedule_time": "03:30",
}

DEFAULT_EMAIL_CONFIG = {
    "imap_host": "",
    "imap_port": 993,
    "imap_user": "",
    "imap_password": "",
    "imap_ssl": True,
    "imap_folder": "INBOX",
    "hours": 24,
    "max_emails": 50,
    "schedule_time": "08:00",
}


# ── Digest 后台任务状态 ───────────────────────────────────────────

digest_task_lock = threading.Lock()
digest_task_status: dict = {}
