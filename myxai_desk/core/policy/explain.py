"""Human-readable explanations for policy decisions."""

from __future__ import annotations

_EXPLANATIONS: dict[str, dict[str, str]] = {
    "PROC_DANGEROUS": {
        "zh": "该操作包含危险命令（删除/格式化/擦除），已被系统安全策略拦截。请使用安全替代方案（移动/重命名），或切换到操作模式。",
        "en": "This operation contains a dangerous command (delete/format/erase) and was blocked by security policy. Use a safe alternative (move/rename), or switch to Operator mode.",
    },
    "PROC_DANGEROUS_CONFIRM": {
        "zh": "该操作包含危险命令（删除/格式化/擦除），需要您确认后执行。实际删除将移入回收站。",
        "en": "This operation contains a dangerous command (delete/format/erase) and requires your confirmation. Actual deletion will move to trash.",
    },
    "PROC_NOT_ALLOWED_IN_MODE": {
        "zh": "当前安全模式不允许执行命令。请切换到 Assistant 或更高模式。",
        "en": "Command execution is not allowed in the current security mode. Switch to Assistant or higher.",
    },
    "PROC_NOT_IN_WHITELIST": {
        "zh": "该命令不在当前模式的白名单中，需要您确认后执行。",
        "en": "This command is not in the current mode's whitelist; confirmation required.",
    },
    "PROC_STRONG_CONFIRM": {
        "zh": "当前模式要求所有命令执行都需要确认。",
        "en": "Current mode requires confirmation for all command executions.",
    },
    "FS_UNSAFE_PATH": {
        "zh": "目标路径不安全（系统目录/根目录），操作已被拦截。",
        "en": "Target path is unsafe (system/root directory); operation blocked.",
    },
    "FS_SYSTEM_WRITE_BLOCKED": {
        "zh": "不允许写入系统目录。",
        "en": "Writing to system directories is not allowed.",
    },
    "FS_OUT_OF_WRITE_SCOPE": {
        "zh": "目标路径超出当前模式允许的写入范围。",
        "en": "Target path is outside the allowed write scope for this mode.",
    },
    "FS_REMOVE_NEEDS_CONFIRM": {
        "zh": "删除操作（移入回收站）需要您确认。",
        "en": "Remove operation (move to trash) requires your confirmation.",
    },
    "FS_WRITE_STRONG_CONFIRM": {
        "zh": "当前模式要求所有文件写入操作都需要确认。",
        "en": "Current mode requires confirmation for all file write operations.",
    },
    "NET_HTTP_NOT_ALLOWED": {
        "zh": "当前安全模式不允许 HTTP 请求。请切换到 Assistant 或更高模式。",
        "en": "HTTP requests are not allowed in current mode. Switch to Assistant or higher.",
    },
    "NET_DOMAIN_NOT_IN_ALLOWLIST": {
        "zh": "目标域名不在允许列表中。",
        "en": "Target domain is not in the allowlist.",
    },
    "NET_SENSITIVE_EXFILTRATION": {
        "zh": "检测到可能的敏感数据外发，已被拦截。",
        "en": "Potential sensitive data exfiltration detected and blocked.",
    },
    "MCP_NOT_ALLOWED_IN_MODE": {
        "zh": "当前安全模式不允许 MCP 调用。",
        "en": "MCP calls are not allowed in current mode.",
    },
    "MCP_SERVER_NOT_IN_ALLOWLIST": {
        "zh": "该 MCP 服务器不在允许列表中。",
        "en": "This MCP server is not in the allowlist.",
    },
    "PROFILE_RAW_DENIED_THIRD_PARTY": {
        "zh": "第三方应用不允许访问原始行为数据。",
        "en": "Third-party apps cannot access raw behavioural data.",
    },
    "PROFILE_RAW_NEEDS_CONFIRM": {
        "zh": "访问原始行为数据需要您确认。",
        "en": "Accessing raw behavioural data requires your confirmation.",
    },
}

_DEFAULT = {
    "zh": "该操作受安全策略限制。",
    "en": "This operation is restricted by security policy.",
}


def explain(reason_code: str, lang: str = "zh") -> str:
    """Return a human-readable explanation for *reason_code*."""
    base_code = reason_code.split(":")[0]
    entry = _EXPLANATIONS.get(base_code, _DEFAULT)
    return entry.get(lang, entry.get("en", reason_code))
