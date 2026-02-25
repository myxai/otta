"""Network / HTTP policy rules — domain allowlist and exfiltration control."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from myxai_desk.core.policy.modes import ModePolicy


_SENSITIVE_DATA_RE = re.compile(
    r'(password|secret|token|api_key|credit.?card|ssn)',
    re.IGNORECASE,
)


def _domain_matches(domain: str, pattern: str) -> bool:
    if pattern == "*":
        return True
    if pattern.startswith("*."):
        return domain == pattern[2:] or domain.endswith("." + pattern[2:])
    return domain == pattern


def evaluate(op: str, args: dict, policy: ModePolicy) -> tuple[str, int, str]:
    """Evaluate a network operation against current mode policy.

    Returns ``(action, risk_score, reason_code)``.
    """
    if op == "search" and policy.net_search_allowed:
        return "ALLOW", 5, "NET_SEARCH_ALLOWED"

    if op in ("http_get", "http_post", "download"):
        if not policy.net_http_allowed:
            return "DENY", 70, "NET_HTTP_NOT_ALLOWED"

        url = args.get("url", "")
        parsed = urlparse(url)
        domain = parsed.hostname or ""

        if policy.net_allowlist:
            if not any(_domain_matches(domain, pat) for pat in policy.net_allowlist):
                return "DENY", 60, f"NET_DOMAIN_NOT_IN_ALLOWLIST:{domain}"

        body = str(args.get("body", args.get("data", "")))
        if _SENSITIVE_DATA_RE.search(body) and not policy.net_exfiltration_allowed:
            return "DENY", 90, "NET_SENSITIVE_EXFILTRATION"

        if policy.confirm_level == "strong":
            return "REQUIRE_CONFIRM", 40, "NET_STRONG_CONFIRM"

        return "ALLOW", 15, "NET_ALLOWED"

    return "ALLOW", 0, "NET_DEFAULT"
