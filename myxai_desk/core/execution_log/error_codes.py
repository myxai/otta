"""Standardised error codes for tool execution failures.

Every tool exception or policy block is mapped to one of these codes so that
aggregate diagnostics (Top-N failure reasons, trends) are meaningful.
"""

from __future__ import annotations

ERROR_CODES: dict[str, str] = {
    "E_PARAM": "参数错误 / schema 不合",
    "E_NOT_FOUND": "文件/资源不存在",
    "E_PERMISSION": "权限/安全模式拒绝",
    "E_TIMEOUT": "超时",
    "E_NETWORK": "网络错误",
    "E_RATE_LIMIT": "限流",
    "E_TOOL_UNAVAILABLE": "工具不可用",
    "E_PARSE": "解析失败",
    "E_VALIDATION": "验证器失败",
    "E_INTERNAL": "内部异常",
    "E_CANCELLED": "用户取消",
    "E_UNKNOWN": "未分类",
}

_EXCEPTION_MAP: dict[type, str] = {
    FileNotFoundError: "E_NOT_FOUND",
    IsADirectoryError: "E_NOT_FOUND",
    NotADirectoryError: "E_NOT_FOUND",
    PermissionError: "E_PERMISSION",
    TimeoutError: "E_TIMEOUT",
    ConnectionError: "E_NETWORK",
    ConnectionRefusedError: "E_NETWORK",
    ConnectionResetError: "E_NETWORK",
    BrokenPipeError: "E_NETWORK",
    ValueError: "E_PARAM",
    TypeError: "E_PARAM",
    KeyError: "E_PARAM",
    json_err_type: "E_PARSE",  # type: ignore[name-defined]  # resolved below
}

try:
    import json

    _EXCEPTION_MAP[json.JSONDecodeError] = "E_PARSE"
except Exception:
    pass

_KEYWORD_MAP: list[tuple[str, str]] = [
    ("not found", "E_NOT_FOUND"),
    ("no such file", "E_NOT_FOUND"),
    ("does not exist", "E_NOT_FOUND"),
    ("permission denied", "E_PERMISSION"),
    ("access denied", "E_PERMISSION"),
    ("forbidden", "E_PERMISSION"),
    ("timed out", "E_TIMEOUT"),
    ("timeout", "E_TIMEOUT"),
    ("rate limit", "E_RATE_LIMIT"),
    ("too many requests", "E_RATE_LIMIT"),
    ("429", "E_RATE_LIMIT"),
    ("connection refused", "E_NETWORK"),
    ("network", "E_NETWORK"),
    ("dns", "E_NETWORK"),
    ("parse error", "E_PARSE"),
    ("invalid json", "E_PARSE"),
    ("decode", "E_PARSE"),
    ("cancelled", "E_CANCELLED"),
    ("canceled", "E_CANCELLED"),
    ("unavailable", "E_TOOL_UNAVAILABLE"),
]


def classify_error(exc: Exception | None = None, message: str = "",
                   tool_name: str = "") -> str:
    """Map an exception or error message to a standard error code."""
    if exc is not None:
        for exc_type, code in _EXCEPTION_MAP.items():
            if isinstance(exc, exc_type):
                return code
        message = message or str(exc)

    msg_lower = message.lower()
    for keyword, code in _KEYWORD_MAP:
        if keyword in msg_lower:
            return code

    return "E_UNKNOWN" if message else ""


def classify_action(action: str, reason_code: str = "") -> str:
    """Map a policy action / guard action to a standard error code."""
    mapping = {
        "DENY": "E_PERMISSION",
        "CAP_BLOCK": "E_TOOL_UNAVAILABLE",
        "GUARD_BLOCK": "E_RATE_LIMIT",
        "SANDBOX_DENY": "E_PERMISSION",
        "CONFIRM": "",
    }
    code = mapping.get(action, "")
    if not code and reason_code:
        rc = reason_code.lower()
        if "permission" in rc or "deny" in rc:
            return "E_PERMISSION"
        if "limit" in rc or "rate" in rc:
            return "E_RATE_LIMIT"
    return code
