"""Network tool verifiers (smart_fetch, web_fetch, web_search)."""

from __future__ import annotations

from myxai_desk.core.execution_log.verifiers.base import BaseVerifier, register_verifier


class HttpGetVerifier(BaseVerifier):
    """Verify HTTP fetch results (smart_fetch, web_fetch)."""

    def tool_names(self) -> list[str]:
        return ["smart_fetch", "web_fetch"]

    def verify(self, tool_name: str, result: str) -> list[dict]:
        checks = []
        has_body = bool(result and len(result.strip()) > 50)
        checks.append({
            "name": "body_length_ok",
            "pass": has_body,
            "detail": f"length={len(result)}" if result else "empty",
        })
        is_error = _is_http_error(result)
        checks.append({
            "name": "no_http_error",
            "pass": not is_error,
            "detail": "" if not is_error else "HTTP error detected",
        })
        return checks


class WebSearchVerifier(BaseVerifier):
    """Verify web search results."""

    def tool_names(self) -> list[str]:
        return ["web_search"]

    def verify(self, tool_name: str, result: str) -> list[dict]:
        checks = []
        has_results = bool(result and len(result.strip()) > 20)
        checks.append({
            "name": "results_non_empty",
            "pass": has_results,
            "detail": f"length={len(result)}" if result else "empty",
        })
        is_error = _is_http_error(result)
        checks.append({
            "name": "no_error_signal",
            "pass": not is_error,
            "detail": "" if not is_error else "error detected",
        })
        return checks


def _is_http_error(result: str) -> bool:
    if not result:
        return True
    low = result[:500].lower()
    signals = ("error", "failed", "timeout", "connection refused",
               "404", "403", "500", "502", "503", "rate limit")
    return any(s in low for s in signals)


register_verifier(HttpGetVerifier())
register_verifier(WebSearchVerifier())
