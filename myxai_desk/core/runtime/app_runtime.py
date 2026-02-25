"""Prompt App Runtime — the unified execution entry point.

Flow: manifest -> capability_factory -> plan -> confirm -> execute -> audit -> output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from myxai_desk.core.audit.ledger import AuditLedger
from myxai_desk.core.audit.undo import UndoRegistry
from myxai_desk.core.policy.engine import decide
from myxai_desk.core.policy.modes import SecurityMode, get_current_mode
from myxai_desk.core.runtime.manifest import AppManifest, load_manifest

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class ExecutionPlan:
    app_id: str
    steps: list[str] = field(default_factory=list)
    affected_scope: str = ""
    risk_score: int = 0
    reversible: bool = True
    requires_confirm: bool = False


@dataclass
class AppResult:
    app_id: str
    success: bool
    output: str = ""
    output_type: str = "text"
    error: str = ""
    action_ids: list[str] = field(default_factory=list)


# ── Capability factory ─────────────────────────────────────────────


def capability_factory(
    permissions: list[str], *, undo: UndoRegistry | None = None, audit: AuditLedger | None = None
) -> dict[str, Any]:
    """Create capability instances restricted to the declared permissions."""
    caps: dict[str, Any] = {}

    perm_set = set(permissions)

    if any(p.startswith("fs.") or p.startswith("file.") for p in perm_set):
        from myxai_desk.core.capabilities.fs import FS

        caps["fs"] = FS(undo_registry=undo, audit_ledger=audit)

    if any(p.startswith("proc.") or p == "proc" for p in perm_set):
        from myxai_desk.core.capabilities.proc import Proc

        caps["proc"] = Proc(undo_registry=undo, audit_ledger=audit)

    if any(p.startswith("search.") for p in perm_set):
        from myxai_desk.core.capabilities.search import SearchCapability

        caps["search"] = SearchCapability(audit_ledger=audit)

    if any(p.startswith("net.") for p in perm_set):
        from myxai_desk.core.capabilities.net import Net

        caps["net"] = Net(audit_ledger=audit)

    if any(p.startswith("profile.") for p in perm_set):
        from myxai_desk.core.capabilities.profile import Profile

        caps["profile"] = Profile()

    if any(p.startswith("notify.") for p in perm_set):
        from myxai_desk.core.capabilities.notify import Notify

        caps["notify"] = Notify()

    if any(p.startswith("cron.") for p in perm_set):
        from myxai_desk.core.capabilities.cron import CronCapability

        caps["cron"] = CronCapability()

    if any(p.startswith("mcp.") for p in perm_set):
        from myxai_desk.core.capabilities.mcp import MCPCapability

        caps["mcp"] = MCPCapability(audit_ledger=audit)

    return caps


# ── Mode check ─────────────────────────────────────────────────────

_MODE_ORDER = [
    SecurityMode.OBSERVER,
    SecurityMode.ASSISTANT,
    SecurityMode.OPERATOR,
    SecurityMode.DEVELOPER,
]


def _mode_sufficient(current: SecurityMode, required_min: str) -> bool:
    """Check if *current* mode meets the minimum requirement."""
    try:
        req = SecurityMode(required_min)
    except ValueError:
        return True
    return _MODE_ORDER.index(current) >= _MODE_ORDER.index(req)


# ── Run App ────────────────────────────────────────────────────────


def run_app(
    app_pkg: Path | AppManifest,
    input_ctx: dict | None = None,
    *,
    agent: Any = None,
) -> AppResult:
    """Execute a Prompt App through the full lifecycle.

    This is the **synchronous** entry point.  For async LLM orchestration the
    caller should use the nanobot agent loop with the generated prompt.
    """
    input_ctx = input_ctx or {}

    # 1. Load manifest
    manifest = app_pkg if isinstance(app_pkg, AppManifest) else load_manifest(app_pkg)

    # 2. Signature verification for official apps
    if manifest.source == "official" and manifest.package_dir:
        from myxai_desk.core.runtime.signing import is_signed, verify_package

        if is_signed(manifest.package_dir) and not verify_package(manifest.package_dir):
            return AppResult(
                app_id=manifest.id,
                success=False,
                error="Official app signature verification failed — package may be tampered",
            )

    # 3. Mode check (renumbered — was 2)
    current_mode = get_current_mode()
    min_mode = manifest.mode_requirements.get("min_mode", "Observer")
    if not _mode_sufficient(current_mode, min_mode):
        return AppResult(
            app_id=manifest.id,
            success=False,
            error=f"Current mode ({current_mode.value}) does not meet "
            f"minimum requirement ({min_mode})",
        )

    # 3. Budget check
    from myxai_desk.core.runtime.budget import check_budget

    budget_ok, budget_reason = check_budget(
        manifest.id,
        tokens_limit=manifest.budgets.tokens_per_day,
        search_limit=manifest.budgets.search_calls_per_day,
    )
    if not budget_ok:
        return AppResult(
            app_id=manifest.id,
            success=False,
            error=f"Budget exceeded: {budget_reason}",
        )

    # 4. Policy pre-check for declared permissions
    audit = AuditLedger()
    undo = UndoRegistry()

    for perm in manifest.permissions:
        cap = perm.split(".")[0]
        op = perm.split(".", 1)[1] if "." in perm else ""
        d = decide(
            app_id=manifest.id,
            source=manifest.source,
            capability=cap,
            op=op,
            args={},
        )
        if d.action == "DENY":
            return AppResult(
                app_id=manifest.id,
                success=False,
                error=f"Permission denied: {perm} — {d.explain}",
            )

    # 5. Prepare capabilities
    capability_factory(manifest.permissions, undo=undo, audit=audit)

    # 6. Build prompt from template
    prompt = manifest.prompt_content
    for key, value in input_ctx.items():
        prompt = prompt.replace("{{" + key + "}}", str(value))

    # 7. Execute via agent (if available) or return prompt for external execution
    if agent is not None:
        try:
            import asyncio

            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    result_text = pool.submit(
                        lambda: asyncio.run(_run_agent(agent, manifest.id, prompt))
                    ).result(timeout=120)
            else:
                result_text = loop.run_until_complete(_run_agent(agent, manifest.id, prompt))
        except Exception as e:
            return AppResult(
                app_id=manifest.id,
                success=False,
                error=f"Agent execution failed: {e}",
            )
    else:
        result_text = prompt

    # 8. Save output
    output_type = "text"
    if manifest.outputs:
        output_type = manifest.outputs[0].type

    return AppResult(
        app_id=manifest.id,
        success=True,
        output=result_text,
        output_type=output_type,
    )


async def _run_agent(agent: Any, app_id: str, prompt: str) -> str:
    """Run the prompt through the nanobot agent."""
    from nanobot.bus.events import InboundMessage

    msg = InboundMessage(
        channel="app",
        chat_id=app_id,
        content=prompt,
    )
    response = await agent._process_message(msg, session_key=f"app:{app_id}")
    return response.content if response else ""


# ── Discovery ──────────────────────────────────────────────────────


def default_search_dirs() -> list[Path]:
    """Return the standard app search directories."""
    from myxai_desk.core.storage.paths import APPS_DIR

    return [
        APPS_DIR / "user",
        APPS_DIR / "third_party",
    ]


def discover_apps(search_dirs: list[Path] | None = None) -> list[AppManifest]:
    """Scan directories for Prompt App packages (containing app.yaml)."""
    if search_dirs is None:
        search_dirs = default_search_dirs()

    seen_ids: set[str] = set()
    manifests: list[AppManifest] = []

    for d in search_dirs:
        if not d.exists():
            continue
        for pkg_dir in sorted(d.iterdir()):
            if pkg_dir.is_dir() and (pkg_dir / "app.yaml").exists():
                try:
                    m = load_manifest(pkg_dir)
                    if m.id not in seen_ids:
                        seen_ids.add(m.id)
                        manifests.append(m)
                except Exception as e:
                    print(f"[app_runtime] Failed to load {pkg_dir}: {e}")
    return manifests
