"""Unified result envelope that wraps raw tool output for healthcheck analytics.

The envelope is created *post-hoc* (after tools.execute returns) so it does not
alter the nanobot tool interface.  Verifiers are looked up from the registry and
run automatically inside ``wrap_result``.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field

log = logging.getLogger("myxai")


@dataclass
class ResultEnvelope:
    ok: bool
    status: str  # "ok" | "soft_fail" | "hard_fail"
    error_code: str | None = None
    error_message: str | None = None
    artifact_type: str = "none"  # file | list | text | dbrow | url | none
    artifact_summary: str = ""
    verifier_pass: bool | None = None  # None = not verified
    verifier_checks: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)


def wrap_result(
    tool_name: str,
    raw_result: str | None,
    *,
    status: str = "ok",
    error_code: str = "",
    error_message: str = "",
) -> ResultEnvelope:
    """Build a ResultEnvelope from a raw tool result string.

    Automatically runs the matching verifier (if one exists in the registry).
    """
    from myxai_desk.core.execution_log.verifiers.base import get_verifier

    ok = status == "ok"
    artifact_type = _guess_artifact_type(tool_name, raw_result)
    artifact_summary = (raw_result or "")[:200]

    envelope = ResultEnvelope(
        ok=ok,
        status=status,
        error_code=error_code or None,
        error_message=error_message or None,
        artifact_type=artifact_type,
        artifact_summary=artifact_summary,
    )

    verifier = get_verifier(tool_name)
    if verifier is not None:
        try:
            checks = verifier.verify(tool_name, raw_result or "")
            envelope.verifier_checks = checks
            envelope.verifier_pass = all(c.get("pass", False) for c in checks)
            if not envelope.verifier_pass:
                envelope.ok = False
                envelope.status = "soft_fail"
                if not envelope.error_code:
                    envelope.error_code = "E_VALIDATION"
        except Exception:
            log.warning("[verifier] %s failed", tool_name, exc_info=True)
            envelope.verifier_pass = None
    else:
        envelope.verifier_pass = None

    return envelope


def _guess_artifact_type(tool_name: str, result: str | None) -> str:
    if not result:
        return "none"
    name = tool_name.lower()
    if "file" in name or "write" in name or "read" in name:
        return "file"
    if "list" in name or "dir" in name:
        return "list"
    if "fetch" in name or "http" in name or "url" in name or "web" in name:
        return "url"
    if "search" in name:
        return "list"
    return "text"
