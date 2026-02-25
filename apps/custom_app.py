"""Custom App — templated chat sessions with typed execution.

A custom app = prompt template + app type + output format + schedule + summary.
Execution is 100% delegated to the nanobot agent (same path as chat).

Every custom app automatically gets a marketplace-compatible package
(``app.yaml`` + ``prompt.md``) written under ``~/.nanobot/apps/user/<app_id>/``
so that it can be discovered by ``myxai_desk.core.runtime.app_runtime.discover_apps``
and governed through the standard manifest-based pipeline.
"""

import json
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

_LOCAL_TZ = timezone(timedelta(hours=8))  # CST
from pathlib import Path

_BASE_DIR = Path.home() / ".nanobot" / "apps" / "custom"
_PARAM_RE = re.compile(r"\{\{([^}]+)\}\}")

try:
    from myxai_desk.core.storage.paths import MARKETPLACE_USER_DIR, ensure_dir
except ImportError:
    MARKETPLACE_USER_DIR = Path.home() / ".nanobot" / "apps" / "user"
    def ensure_dir(p: Path) -> Path:
        p.mkdir(parents=True, exist_ok=True)
        return p

# ── Marketplace package sync ───────────────────────────────────────────

_OUTPUT_FMT_TO_MANIFEST: dict[str, str] = {
    "report":       "report.html",
    "notification": "notification",
    "text":         "text",
}

_SECURITY_MODE_PERMISSIONS: dict[str, list[str]] = {
    "Observer":  ["search.web", "net.http_get", "notify.push", "fs.read",
                  "profile.read.summary"],
    "Assistant": ["search.web", "net.http_get", "notify.push", "fs.read",
                  "fs.write", "profile.read.summary", "profile.read.topics"],
    "Operator":  ["search.web", "net.http_get", "notify.push", "fs.read",
                  "fs.write", "fs.delete", "proc.exec",
                  "profile.read.summary", "profile.read.topics"],
    "Developer": ["search.web", "net.http_get", "notify.push", "fs.read",
                  "fs.write", "fs.delete", "proc.exec", "mcp.call",
                  "profile.read.summary", "profile.read.topics"],
}


def _schedule_to_cron(schedule: dict) -> str:
    """Convert custom app schedule dict to a cron expression."""
    if not schedule.get("enabled"):
        return ""
    time_str = schedule.get("time", "")
    if not time_str or ":" not in time_str:
        return ""
    hh, mm = time_str.split(":")[:2]
    mode = schedule.get("mode", "daily")
    if mode == "daily":
        return f"{mm} {hh} * * *"
    if mode == "weekly":
        dow = schedule.get("day_of_week", 0)
        return f"{mm} {hh} * * {dow}"
    if mode == "monthly":
        dom = schedule.get("day_of_month", 1)
        return f"{mm} {hh} {dom} * *"
    if mode == "interval":
        return f"{mm} {hh} * * *"
    return ""


def _build_manifest_dict(app: dict) -> dict[str, Any]:
    """Build an ``app.yaml``-compatible dict from a custom app record."""
    sec_mode = app.get("security_mode") or "Observer"
    permissions = _SECURITY_MODE_PERMISSIONS.get(sec_mode,
                  _SECURITY_MODE_PERMISSIONS["Observer"])

    triggers: list[dict] = [{"type": "manual"}]
    sched = app.get("schedule", {})
    cron_expr = _schedule_to_cron(sched)
    if cron_expr:
        triggers.append({"type": "cron", "cron": cron_expr})

    out_type = _OUTPUT_FMT_TO_MANIFEST.get(
        app.get("output_format", "text"), "text")

    return {
        "id": app["id"],
        "name": app.get("name", app["id"]),
        "name_en": app.get("name", app["id"]),
        "version": "1.0.0",
        "source": "user",
        "entry": "prompt",
        "prompt_file": "prompt.md",
        "description": app.get("name", ""),
        "description_en": "",
        "author": "user",
        "triggers": triggers,
        "permissions": permissions,
        "budgets": {
            "tokens_per_day": 200000,
            "search_calls_per_day": 100,
        },
        "mode_requirements": {
            "min_mode": sec_mode,
        },
        "data_policy": {
            "allow_raw_history": False,
            "allow_network_exfiltration": False,
        },
        "outputs": [
            {"type": out_type, "path": f"reports/{{{{date}}}}_{app['id']}.html"}
            if out_type == "report.html"
            else {"type": out_type},
        ],
        "ui": {
            "icon": app.get("icon", "🤖"),
            "category": "custom",
        },
    }


def _build_prompt_md(app: dict) -> str:
    """Generate the ``prompt.md`` content from a custom app's template."""
    fmt = app.get("output_format", "text")
    fmt_label = OUTPUT_FORMATS.get(fmt, {}).get("label_zh", "纯文本")
    suffix = OUTPUT_FORMATS.get(fmt, {}).get("suffix", "")

    lines = [
        f"# {app.get('name', '自定义应用')}",
        "",
        "你正在执行用户自定义的 Prompt 应用。",
        "",
        "## 应用信息",
        f"- 应用名称：{app.get('name', '')}",
        f"- 输出格式：{fmt_label}",
        "",
        "## 用户模板",
        "",
        app.get("prompt_template", ""),
        "",
    ]

    if suffix:
        lines += [
            "## 输出要求",
            "",
            suffix.lstrip("，"),
            "",
        ]

    lines += [
        "## 约束",
        "",
        "- 严格按照用户模板中的指令执行",
        "- 输出格式必须符合上述要求",
        "- 如果模板中包含搜索或网络查询需求，使用可用工具完成",
        "- 所有数据来源必须真实可查，禁止编造",
    ]
    return "\n".join(lines) + "\n"


def sync_marketplace_package(app: dict) -> Path:
    """Write (or overwrite) the marketplace package for a custom app.

    Returns the package directory path.
    """
    try:
        import yaml
    except ImportError:
        yaml = None  # type: ignore[assignment]

    pkg_dir = MARKETPLACE_USER_DIR / app["id"]
    ensure_dir(pkg_dir)

    manifest = _build_manifest_dict(app)

    if yaml is not None:
        (pkg_dir / "app.yaml").write_text(
            yaml.dump(manifest, allow_unicode=True, sort_keys=False,
                      default_flow_style=False),
            encoding="utf-8",
        )
    else:
        (pkg_dir / "app.yaml").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    (pkg_dir / "prompt.md").write_text(
        _build_prompt_md(app), encoding="utf-8",
    )
    return pkg_dir


def remove_marketplace_package(app_id: str) -> bool:
    """Remove the marketplace package for a custom app."""
    from apps.safe_fs import safe_remove
    pkg_dir = MARKETPLACE_USER_DIR / app_id
    if pkg_dir.exists():
        safe_remove(pkg_dir)
        return True
    return False


def migrate_existing_apps() -> list[str]:
    """One-time migration: generate marketplace packages for all existing
    custom apps that don't have one yet.

    Returns list of migrated app IDs.
    """
    migrated: list[str] = []
    for app in list_apps():
        pkg_dir = MARKETPLACE_USER_DIR / app["id"]
        if not (pkg_dir / "app.yaml").exists():
            sync_marketplace_package(app)
            migrated.append(app["id"])
    return migrated


# ── Constants ──────────────────────────────────────────────────────────

OUTPUT_FORMATS = {
    "report":       {"label_zh": "HTML报告", "label_en": "HTML Report",
                     "suffix": "，请以结构化HTML报告格式输出，包含标题、分节和数据来源"},
    "notification": {"label_zh": "通知",     "label_en": "Notification",
                     "suffix": "，请简要输出核心结论，适合通知推送"},
    "text":         {"label_zh": "纯文本",   "label_en": "Plain Text",
                     "suffix": ""},
}

# Schedule modes
SCHEDULE_MODES = {
    "daily":    {"label_zh": "每天",       "label_en": "Daily"},
    "weekly":   {"label_zh": "每周",       "label_en": "Weekly"},
    "monthly":  {"label_zh": "每月",       "label_en": "Monthly"},
    "interval": {"label_zh": "间隔(天)",   "label_en": "Interval (days)"},
}

WEEKDAYS_ZH = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

# ── Persistence helpers ─────────────────────────────────────────────

def _ensure_dirs(app_id: str | None = None):
    _BASE_DIR.mkdir(parents=True, exist_ok=True)
    if app_id:
        (_BASE_DIR / app_id / "reports").mkdir(parents=True, exist_ok=True)


def _app_file(app_id: str) -> Path:
    return _BASE_DIR / f"{app_id}.json"


def _reports_dir(app_id: str) -> Path:
    return _BASE_DIR / app_id / "reports"


def _save(app: dict):
    _app_file(app["id"]).write_text(
        json.dumps(app, ensure_ascii=False, indent=2), encoding="utf-8",
    )


# ── CRUD ────────────────────────────────────────────────────────────

_DEFAULT_SCHEDULE = {
    "enabled": False,
    "mode": "daily",
    "time": "",
    "day_of_week": 0,
    "day_of_month": 1,
    "interval_days": 1,
    "last_triggered": None,
    # catch-up scheduling
    "catchup_policy": "LATEST_ONLY",   # NONE / LATEST_ONLY / ALL_MISSED
    "catchup_window_hours": 24,
    "max_catchup_runs": 1,
}

_DEFAULT_SUMMARY = {
    "enabled": False,
    "prompt": "",
    "output_format": "html",
    "range_days": 7,
    "schedule": dict(_DEFAULT_SCHEDULE),
}


def create_app(name: str, prompt_template: str, icon: str = "🤖",
               output_format: str = "text",
               schedule: dict | None = None,
               summary: dict | None = None,
               security_mode: str | None = None,
               inject_profile: bool = False,
               **_extra) -> dict:
    _ensure_dirs()
    app_id = "capp_" + uuid.uuid4().hex[:10]
    app = {
        "id": app_id,
        "name": name,
        "icon": icon,
        "prompt_template": prompt_template,
        "output_format": output_format,
        "parameters": extract_parameters(prompt_template),
        "schedule": {**_DEFAULT_SCHEDULE, **(schedule or {})},
        "summary": {**_DEFAULT_SUMMARY, **(summary or {})},
        "security_mode": security_mode,
        "inject_profile": inject_profile,
        "created_at": datetime.now(_LOCAL_TZ).isoformat(),
        "last_run": None,
    }
    _save(app)
    if security_mode:
        try:
            from myxai_desk.core.policy.modes import SecurityMode, set_app_mode
            set_app_mode(app_id, SecurityMode(security_mode))
        except Exception:
            pass
    try:
        sync_marketplace_package(app)
    except Exception:
        pass
    return app


def update_app(app_id: str, **kwargs) -> dict | None:
    app = get_app(app_id)
    if not app:
        return None
    allowed = ("name", "icon",
               "prompt_template", "output_format", "schedule", "summary",
               "param_values", "param_groups", "security_mode", "inject_profile")
    for key in allowed:
        if key in kwargs:
            if key == "schedule":
                app["schedule"] = {**_DEFAULT_SCHEDULE, **app.get("schedule", {}), **kwargs[key]}
            elif key == "summary":
                cur = app.get("summary") or dict(_DEFAULT_SUMMARY)
                incoming = kwargs[key]
                if "schedule" in incoming:
                    incoming["schedule"] = {**_DEFAULT_SCHEDULE, **cur.get("schedule", {}), **incoming["schedule"]}
                app["summary"] = {**cur, **incoming}
            else:
                app[key] = kwargs[key]
    if "prompt_template" in kwargs:
        app["parameters"] = extract_parameters(kwargs["prompt_template"])
    if "security_mode" in kwargs:
        sm = kwargs["security_mode"]
        try:
            from myxai_desk.core.policy.modes import SecurityMode, set_app_mode, clear_app_mode
            if sm:
                set_app_mode(app_id, SecurityMode(sm))
            else:
                clear_app_mode(app_id)
        except Exception:
            pass
    _save(app)
    try:
        sync_marketplace_package(app)
    except Exception:
        pass
    return app


def delete_app(app_id: str) -> bool:
    from apps.safe_fs import safe_remove
    fp = _app_file(app_id)
    if not fp.exists():
        return False
    safe_remove(fp)
    d = _BASE_DIR / app_id
    if d.exists():
        safe_remove(d)
    try:
        remove_marketplace_package(app_id)
    except Exception:
        pass
    return True


def list_apps() -> list[dict]:
    _ensure_dirs()
    apps = []
    for fp in _BASE_DIR.glob("capp_*.json"):
        try:
            apps.append(json.loads(fp.read_text(encoding="utf-8")))
        except Exception:
            pass
    apps.sort(key=lambda a: a.get("created_at", ""), reverse=True)
    return apps


def get_app(app_id: str) -> dict | None:
    fp = _app_file(app_id)
    if fp.exists():
        try:
            return json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


def set_last_run(app_id: str, ts: str | None = None):
    app = get_app(app_id)
    if not app:
        return
    app["last_run"] = ts or datetime.now(_LOCAL_TZ).isoformat()
    _save(app)


# ── Template helpers ────────────────────────────────────────────────

def extract_parameters(template: str) -> list[dict]:
    seen: set[str] = set()
    params: list[dict] = []
    for m in _PARAM_RE.finditer(template):
        name = m.group(1)
        if name in seen:
            continue
        seen.add(name)
        params.append({"name": name, "label": name, "default": ""})
    return params


def fill_template(template: str, param_values: dict) -> str:
    def _repl(m):
        return str(param_values.get(m.group(1), m.group(0)))
    return _PARAM_RE.sub(_repl, template)


def build_message(app: dict, param_values: dict) -> str:
    """Build the chat message: filled template + output suffix."""
    msg = fill_template(app["prompt_template"], param_values)

    # Inject profile context if enabled
    if app.get("inject_profile"):
        try:
            from myxai_desk.core.capabilities.profile import Profile
            profile = Profile()
            summary = profile.get_summary()
            if summary and summary.get("top_work_interests"):
                topics = summary.get("top_work_interests", [])[:5] + summary.get("top_study_interests", [])[:3]
                if topics:
                    profile_ctx = "[用户画像] 近期关注: " + ", ".join(topics)
                    msg = profile_ctx + "\n\n" + msg
        except Exception:
            pass

    fmt = app.get("output_format", "text")
    suffix = OUTPUT_FORMATS.get(fmt, {}).get("suffix", "")
    if suffix:
        msg += suffix
    return msg


# ── Schedule helpers ────────────────────────────────────────────────

def should_trigger(schedule: dict, now: datetime | None = None) -> bool:
    """Check if a schedule should trigger at *now*.

    When catchup_policy is NONE (or the SchedulerService is unavailable),
    this falls back to exact-minute matching for backward compatibility.
    Otherwise it delegates to the SchedulerService due-slot computation.
    """
    if not schedule.get("enabled"):
        return False
    sched_time = schedule.get("time", "")
    if not sched_time:
        return False

    now = now or datetime.now()
    current_hm = now.strftime("%H:%M")
    if current_hm != sched_time:
        return False

    mode = schedule.get("mode", "daily")

    if mode == "daily":
        return True

    if mode == "weekly":
        dow = schedule.get("day_of_week", 0)
        return now.weekday() == dow

    if mode == "monthly":
        dom = schedule.get("day_of_month", 1)
        return now.day == dom

    if mode == "interval":
        interval = max(1, schedule.get("interval_days", 1))
        last = schedule.get("last_triggered")
        if not last:
            return True
        try:
            last_dt = datetime.fromisoformat(last)
            delta = (now - last_dt).days
            return delta >= interval
        except Exception:
            return True

    return False


def build_task_descriptor(app: dict, schedule_key: str = "schedule"):
    """Build a SchedulerService TaskDescriptor from a custom app record.

    Returns None if the schedule is not enabled or misconfigured.
    """
    try:
        from myxai_desk.core.scheduler_service import TaskDescriptor, CATCHUP_DEFAULTS
    except ImportError:
        return None

    sched = (app.get(schedule_key) if schedule_key == "schedule"
             else app.get("summary", {}).get("schedule"))
    if not sched or not sched.get("enabled"):
        return None

    cron_expr = _schedule_to_cron(sched)

    return TaskDescriptor(
        task_id=app["id"] if schedule_key == "schedule" else f"{app['id']}__summary",
        schedule=sched,
        cron_expr=cron_expr,
        created_at=app.get("created_at", ""),
        last_success_at=sched.get("last_triggered"),
        catchup_policy=sched.get("catchup_policy", CATCHUP_DEFAULTS["catchup_policy"]),
        catchup_window_hours=sched.get("catchup_window_hours", CATCHUP_DEFAULTS["catchup_window_hours"]),
        max_catchup_runs=sched.get("max_catchup_runs", CATCHUP_DEFAULTS["max_catchup_runs"]),
        extra={"kind": "custom" if schedule_key == "schedule" else "custom_summary",
               "app": app, "schedule_key": schedule_key},
    )


def mark_triggered(app_id: str, schedule_key: str = "schedule"):
    """Update last_triggered timestamp on the schedule."""
    app = get_app(app_id)
    if not app:
        return
    sched = app.get(schedule_key) if schedule_key == "schedule" else app.get("summary", {}).get("schedule")
    if sched:
        sched["last_triggered"] = datetime.now(_LOCAL_TZ).isoformat()
    if schedule_key == "schedule":
        app["schedule"] = sched
    else:
        if "summary" not in app:
            app["summary"] = dict(_DEFAULT_SUMMARY)
        app["summary"]["schedule"] = sched
    _save(app)


# ── Reports ─────────────────────────────────────────────────────────

def _params_slug(params_used: dict) -> str:
    """Build a short filesystem-safe slug from param values."""
    if not params_used:
        return ""
    vals = [str(v).strip() for v in params_used.values() if str(v).strip()]
    if not vals:
        return ""
    raw = "_".join(vals)
    safe = re.sub(r'[\\/:*?"<>|\s]+', "_", raw).strip("_")
    return safe[:60]


def _report_key(date_str: str, report_type: str, params_used: dict | None = None) -> str:
    slug = _params_slug(params_used or {})
    if slug:
        return f"{date_str}_{slug}_{report_type}"
    return f"{date_str}_{report_type}"


def save_report(app_id: str, content: str, params_used: dict,
                report_type: str = "run") -> dict:
    """Save a report. Key includes param values so each group gets its own file.

    Any existing read mark for this key is cleared so the refreshed report
    shows as unread again.
    """
    _ensure_dirs(app_id)
    now = datetime.now(_LOCAL_TZ)
    date_str = now.strftime("%Y-%m-%d")
    key = _report_key(date_str, report_type, params_used)
    report = {
        "key": key,
        "date": date_str,
        "type": report_type,
        "content": content,
        "params_used": params_used,
        "generated_at": now.isoformat(),
    }
    (_reports_dir(app_id) / f"{key}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    # Clear read mark so a regenerated report appears as unread
    app = get_app(app_id)
    if app:
        read_set = set(app.get("read_reports", []))
        if key in read_set:
            read_set.discard(key)
            app["read_reports"] = list(read_set)
            _save(app)
    return report


def list_reports(app_id: str, report_type: str | None = None) -> list[dict]:
    d = _reports_dir(app_id)
    if not d.exists():
        return []
    app = get_app(app_id)
    read_set = set(app.get("read_reports", [])) if app else set()
    reports = []
    for fp in sorted(d.glob("*.json"), reverse=True):
        try:
            meta = json.loads(fp.read_text(encoding="utf-8"))
            rtype = meta.get("type", "run")
            if report_type and rtype != report_type:
                continue
            key = meta.get("key", fp.stem)
            reports.append({
                "date": meta.get("date", ""),
                "key": key,
                "type": rtype,
                "generated_at": meta.get("generated_at", ""),
                "params_used": meta.get("params_used", {}),
                "read": key in read_set,
            })
        except Exception:
            pass
    return reports


def get_report(app_id: str, key: str) -> dict | None:
    fp = _reports_dir(app_id) / f"{key}.json"
    if fp.exists():
        try:
            return json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


def delete_report(app_id: str, key: str) -> bool:
    """Move a single report file to trash."""
    from apps.safe_fs import safe_remove
    fp = _reports_dir(app_id) / f"{key}.json"
    if not fp.exists():
        return False
    safe_remove(fp)
    app = get_app(app_id)
    if app:
        read_set = set(app.get("read_reports", []))
        read_set.discard(key)
        app["read_reports"] = list(read_set)
        _save(app)
    return True


def mark_report_read(app_id: str, key: str):
    """Mark a report as read."""
    app = get_app(app_id)
    if not app:
        return
    read_set = set(app.get("read_reports", []))
    read_set.add(key)
    app["read_reports"] = list(read_set)
    _save(app)


def unread_count(app_id: str) -> int:
    """Count unread reports for an app."""
    reports = list_reports(app_id)
    return sum(1 for r in reports if not r.get("read"))


def all_unread_counts() -> dict[str, int]:
    """Return {app_id: unread_count} for all custom apps."""
    counts = {}
    for app in list_apps():
        c = unread_count(app["id"])
        if c > 0:
            counts[app["id"]] = c
    return counts


# ── Summary ─────────────────────────────────────────────────────────

def build_summary_prompt(app: dict, max_reports: int = 30) -> str | None:
    """Build a summary prompt from historical reports within configured range.
    Returns None if no reports or summary not configured."""
    summary_cfg = app.get("summary", {})
    if not summary_cfg.get("enabled"):
        return None

    user_prompt = summary_cfg.get("prompt", "").strip()
    if not user_prompt:
        user_prompt = "请对以下历史执行结果进行综合总结分析"

    range_days = summary_cfg.get("range_days", 7)
    output_format = summary_cfg.get("output_format", "html")

    cutoff = (datetime.now(_LOCAL_TZ) - timedelta(days=range_days)).strftime("%Y-%m-%d")

    all_reports = list_reports(app["id"], report_type="run")
    reports = [r for r in all_reports if r.get("date", "") >= cutoff][:max_reports]
    if not reports:
        return None

    d = _reports_dir(app["id"])
    excerpts: list[str] = []
    for r in reports:
        fp = d / f"{r['key']}.json"
        if not fp.exists():
            continue
        try:
            full = json.loads(fp.read_text(encoding="utf-8"))
            content = full.get("content", "")
            if len(content) > 3000:
                content = content[:3000] + "…（截断）"
            excerpts.append(f"### {r['date']}\n{content}")
        except Exception:
            pass

    if not excerpts:
        return None

    fmt_instruction = (
        "请以结构化 HTML 格式输出总结报告（使用 <h2>/<h3>/<ul>/<table> 等标签，不要输出 ```html 代码块标记，直接输出 HTML 内容）。"
        if output_format == "html"
        else "请以纯文本格式输出总结报告。"
    )

    body = "\n\n---\n\n".join(excerpts)
    constraints = (
        "\n\n【重要约束】\n"
        "- 你的总结必须且只能基于上述提供的报告内容，严禁编造、推测或补充报告中未出现的信息。\n"
        '- 如果报告数据不足以得出某个结论，请明确说明"数据不足"，而不是猜测。\n'
        "- 不要引用任何上述报告中未提及的链接、数据或事实。"
    )
    return (
        f"{user_prompt}\n\n"
        f"应用名称：{app['name']}\n"
        f"任务模板：{app['prompt_template']}\n"
        f"分析范围：最近 {range_days} 天\n\n"
        f"以下是该时间范围内的 {len(excerpts)} 份执行报告：\n\n"
        f"{body}\n\n"
        f"{fmt_instruction}"
        f"{constraints}"
    )
