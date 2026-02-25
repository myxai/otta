"""App execution governance — policy + audit + mode gating for ALL apps.

Every app execution (hardcoded or custom/prompt) MUST pass through this
module before doing any work.  This ensures:

  1. Security mode check — is the app allowed in the current mode?
  2. Policy pre-check — are the app's required capabilities permitted?
  3. Budget check — has the app exceeded its daily limits?
  4. Audit logging — every app run is recorded
  5. Profile event — app run is tracked for user profile

Usage in route handlers:

    from myxai_desk.core.runtime.app_governance import gate_app_run

    decision = gate_app_run("daily_digest", source="official",
                            capabilities=["search.web", "profile.read.summary", "net.http_get"])
    if not decision["allowed"]:
        return jsonify({"error": decision["reason"]}), 403
    # ... proceed with app execution ...
    finish_app_run("daily_digest", success=True)
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

# ── Fallback declarations (used ONLY when no app.yaml is found) ───

_FALLBACK_DECLARATIONS: dict[str, dict] = {
    "daily_digest": {
        "source": "official",
        "min_mode": "Observer",
        "capabilities": ["profile.read.summary", "search.web", "net.http_get", "notify.push"],
    },
    "web_monitor": {
        "source": "official",
        "min_mode": "Observer",
        "capabilities": ["net.http_get", "notify.push", "fs.write"],
    },
    "email_summary": {
        "source": "official",
        "min_mode": "Assistant",
        "capabilities": ["net.http_get", "notify.push"],
    },
}

CUSTOM_APP_DEFAULT_CAPABILITIES = ["search.web", "net.http_get", "notify.push", "fs.read"]

def _find_manifest_dir(app_id: str) -> Path | None:
    """Locate the app.yaml package directory for *app_id*.

    Search order:
      1. ``~/.nanobot/apps/user/<app_id>/``
      2. ``~/.nanobot/apps/third_party/<app_id>/``
    """
    try:
        from myxai_desk.core.storage.paths import APPS_DIR
    except ImportError:
        APPS_DIR = Path.home() / ".nanobot" / "apps"

    user_pkg = APPS_DIR / "user" / app_id
    if (user_pkg / "app.yaml").exists():
        return user_pkg

    tp_pkg = APPS_DIR / "third_party" / app_id
    if (tp_pkg / "app.yaml").exists():
        return tp_pkg

    return None


def _manifest_to_decl(manifest_dir: Path) -> dict | None:
    """Read an ``app.yaml`` and return a normalised declaration dict."""
    yaml_path = manifest_dir / "app.yaml"
    if not yaml_path.exists():
        return None
    try:
        import yaml
        raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    except ImportError:
        import json
        raw = json.loads(yaml_path.read_text(encoding="utf-8"))
    except Exception:
        return None

    if not isinstance(raw, dict):
        return None

    return {
        "source": raw.get("source", "user"),
        "min_mode": raw.get("mode_requirements", {}).get("min_mode", "Observer"),
        "capabilities": raw.get("permissions", CUSTOM_APP_DEFAULT_CAPABILITIES),
        "budgets": raw.get("budgets", {}),
    }


def _get_app_decl(app_id: str, source: str = "",
                  capabilities: list[str] | None = None) -> dict:
    """Get the capability declaration for *app_id*.

    Resolution order:
      1. App manifest (``app.yaml``) — authoritative
      2. Hardcoded fallback table (``_FALLBACK_DECLARATIONS``)
      3. Generic custom-app defaults
    """
    pkg_dir = _find_manifest_dir(app_id)
    if pkg_dir is not None:
        decl = _manifest_to_decl(pkg_dir)
        if decl is not None:
            if capabilities:
                decl["capabilities"] = capabilities
            if source:
                decl["source"] = source
            return decl

    if app_id in _FALLBACK_DECLARATIONS:
        decl = dict(_FALLBACK_DECLARATIONS[app_id])
        if capabilities:
            decl["capabilities"] = capabilities
        if source:
            decl["source"] = source
        return decl

    return {
        "source": source or ("user" if app_id.startswith("capp_") else "official"),
        "min_mode": "Observer",
        "capabilities": capabilities or CUSTOM_APP_DEFAULT_CAPABILITIES,
    }


# ── Gate (pre-execution) ──────────────────────────────────────────

def gate_app_run(
    app_id: str,
    *,
    source: str = "",
    capabilities: list[str] | None = None,
) -> dict:
    """Check if *app_id* is allowed to run under current governance.

    Returns ``{"allowed": True/False, "reason": str, "warnings": [...]}``.
    """
    decl = _get_app_decl(app_id, source, capabilities)
    warnings: list[str] = []

    # 1. Security mode check — uses per-app mode if set, else global
    effective_mode = None
    try:
        from myxai_desk.core.policy.modes import (
            SecurityMode, get_effective_mode, mode_index,
        )
        effective_mode = get_effective_mode(app_id)
        try:
            required = SecurityMode(decl["min_mode"])
        except ValueError:
            required = SecurityMode.OBSERVER

        if mode_index(effective_mode) < mode_index(required):
            return {
                "allowed": False,
                "reason": (f"有效安全模式 {effective_mode.value} 不满足应用要求的最低模式 "
                           f"{required.value}"),
                "warnings": [],
            }
    except Exception as e:
        warnings.append(f"Mode check skipped: {e}")

    # 2. Policy pre-check for each declared capability (using per-app mode)
    denied_caps: list[str] = []
    confirm_caps: list[str] = []
    try:
        from myxai_desk.core.policy.engine import decide
        for cap_str in decl.get("capabilities", []):
            parts = cap_str.split(".", 1)
            cap = parts[0]
            op = parts[1] if len(parts) > 1 else ""
            d = decide(
                app_id=app_id,
                source=decl.get("source", "official"),
                mode=effective_mode,
                capability=cap,
                op=op,
                args={},
            )
            if d.action == "DENY":
                denied_caps.append(f"{cap_str}: {d.explain}")
            elif d.action == "REQUIRE_CONFIRM":
                confirm_caps.append(cap_str)
    except Exception as e:
        warnings.append(f"Policy check error: {e}")

    if denied_caps:
        return {
            "allowed": False,
            "reason": f"策略拒绝: {'; '.join(denied_caps)}",
            "warnings": warnings,
        }

    if confirm_caps:
        warnings.append(f"以下能力需要确认: {', '.join(confirm_caps)}")

    # 3. Budget check (for apps with declared budgets)
    try:
        from myxai_desk.core.runtime.budget import check_budget
        # Use reasonable defaults for hardcoded apps
        ok, reason = check_budget(app_id, tokens_limit=200000, search_limit=100)
        if not ok:
            return {
                "allowed": False,
                "reason": f"预算超限: {reason}",
                "warnings": warnings,
            }
    except Exception as e:
        warnings.append(f"Budget check skipped: {e}")

    # 4. Audit: log the app run attempt
    try:
        from myxai_desk.core.audit.ledger import AuditLedger
        AuditLedger().append_entry(
            capability="app.run",
            args={"app_id": app_id, "source": decl.get("source", "")},
            action_id="",
            result_summary="gate_passed",
        )
    except Exception:
        pass

    return {"allowed": True, "reason": "", "warnings": warnings}


# ── Finish (post-execution) ───────────────────────────────────────

def finish_app_run(
    app_id: str,
    *,
    success: bool = True,
    error: str = "",
    tokens_used: int = 0,
) -> None:
    """Record that an app run has completed."""
    # Audit entry
    try:
        from myxai_desk.core.audit.ledger import AuditLedger
        AuditLedger().append_entry(
            capability="app.run.complete",
            args={"app_id": app_id, "success": success},
            action_id="",
            result_summary=error if error else "ok",
        )
    except Exception:
        pass

    # Budget recording
    if tokens_used > 0:
        try:
            from myxai_desk.core.runtime.budget import record_tokens
            record_tokens(app_id, tokens_used)
        except Exception:
            pass

    # Profile event
    try:
        from myxai_desk.core.profile.events import EventStore, AppRun
        EventStore().append(AppRun(
            app_id=app_id,
            ts=str(time.time()),
            inputs_digest="",
            outputs_digest="ok" if success else error[:100],
        ))
    except Exception:
        pass
