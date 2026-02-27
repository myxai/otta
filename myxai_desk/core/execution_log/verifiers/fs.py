"""File-system tool verifiers (read_file, write_file, list_dir)."""

from __future__ import annotations

from myxai_desk.core.execution_log.verifiers.base import BaseVerifier, register_verifier


class ReadFileVerifier(BaseVerifier):
    def tool_names(self) -> list[str]:
        return ["read_file"]

    def verify(self, tool_name: str, result: str) -> list[dict]:
        checks = []
        has_content = bool(result and len(result.strip()) > 0)
        checks.append({
            "name": "result_non_empty",
            "pass": has_content,
            "detail": f"length={len(result)}" if result else "empty",
        })
        is_error = _looks_like_error(result)
        checks.append({
            "name": "no_error_signal",
            "pass": not is_error,
            "detail": "" if not is_error else "error keywords detected",
        })
        return checks


class WriteFileVerifier(BaseVerifier):
    def tool_names(self) -> list[str]:
        return ["write_file", "edit_file"]

    def verify(self, tool_name: str, result: str) -> list[dict]:
        checks = []
        has_result = bool(result and len(result.strip()) > 0)
        checks.append({
            "name": "result_non_empty",
            "pass": has_result,
            "detail": f"length={len(result)}" if result else "empty",
        })
        is_error = _looks_like_error(result)
        checks.append({
            "name": "no_error_signal",
            "pass": not is_error,
            "detail": "" if not is_error else "error keywords detected",
        })
        return checks


class ListDirVerifier(BaseVerifier):
    def tool_names(self) -> list[str]:
        return ["list_dir"]

    def verify(self, tool_name: str, result: str) -> list[dict]:
        checks = []
        has_content = bool(result and len(result.strip()) > 0)
        checks.append({
            "name": "result_non_empty",
            "pass": has_content,
            "detail": f"length={len(result)}" if result else "empty",
        })
        is_error = _looks_like_error(result)
        checks.append({
            "name": "no_error_signal",
            "pass": not is_error,
            "detail": "" if not is_error else "error keywords detected",
        })
        return checks


def _looks_like_error(result: str) -> bool:
    if not result:
        return False
    low = result[:300].lower()
    signals = ("error:", "traceback", "exception", "permission denied", "not found",
               "no such file", "does not exist", "failed to")
    return any(s in low for s in signals)


register_verifier(ReadFileVerifier())
register_verifier(WriteFileVerifier())
register_verifier(ListDirVerifier())
