"""SmartFetchTool + FetchGuard — URL fetching with anti-bot detection and execution control.

SmartFetchTool wraps nanobot's WebFetchTool with:
  - Captcha / anti-bot / WAF page detection
  - Minimum content length enforcement
  - Structured ok/blocked/error results

FetchGuard provides turn-level execution control:
  - Per-URL fetch attempt limits (prevents infinite retry loops)
  - Per-turn total fetch tool call limits
  - No-source-no-write: blocks write_file when fetches all failed
"""

import json
import re
from typing import Any

from nanobot.agent.tools.base import Tool

_BLOCK_PATTERNS = re.compile(
    r"captcha|recaptcha|hcaptcha|verify.{0,20}human|are you a robot|"
    r"access.denied|challenge.{0,10}required|blocked|"
    r"just a moment|checking your browser|"
    r"cloudflare|incapsula|sucuri|akamai.{0,10}ghost|"
    r"DDoS.protection|bot.detection|"
    r"验证码|人机验证|访问被拒绝|请完成安全验证|"
    r"请输入验证码|安全检查",
    re.IGNORECASE,
)

_MIN_CONTENT_LENGTH = 200


class SmartFetchTool(Tool):
    """Fetch URL with captcha/anti-bot detection and structured results."""

    name = "smart_fetch"
    description = (
        "Fetch a URL and extract readable content. Automatically detects "
        "captcha/anti-bot pages and returns structured ok/blocked status. "
        "ALWAYS use this instead of exec+curl for URL fetching."
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to fetch"},
            "extract_mode": {
                "type": "string",
                "enum": ["markdown", "text"],
                "default": "markdown",
                "description": "Output format: markdown or plain text",
            },
        },
        "required": ["url"],
    }

    def __init__(
        self,
        min_content_length: int = 200,
        max_chars: int = 50000,
        max_output_chars: int = 5000,
    ):
        self._min_length = min_content_length
        self._max_chars = max_chars
        self._max_output = max_output_chars
        self._web_fetch = None

    def _get_web_fetch(self):
        if self._web_fetch is None:
            from nanobot.agent.tools.web import WebFetchTool

            self._web_fetch = WebFetchTool(max_chars=self._max_chars)
        return self._web_fetch

    async def execute(self, url: str, extract_mode: str = "markdown", **kwargs: Any) -> str:
        wf = self._get_web_fetch()

        try:
            raw_result = await wf.execute(url=url, extractMode=extract_mode)
        except Exception as e:
            return json.dumps(
                {
                    "ok": False,
                    "blocked": False,
                    "url": url,
                    "text": "",
                    "error": f"FETCH_FAILED: {e}",
                    "suggestion": "URL 无法访问，请检查链接是否正确或尝试其他来源。",
                },
                ensure_ascii=False,
            )

        try:
            data = json.loads(raw_result)
        except (json.JSONDecodeError, TypeError):
            data = {"text": str(raw_result), "url": url}

        if "error" in data and data["error"]:
            return json.dumps(
                {
                    "ok": False,
                    "blocked": False,
                    "url": url,
                    "text": "",
                    "error": f"FETCH_ERROR: {data['error']}",
                    "suggestion": "抓取失败，请检查 URL 或换用其他来源。",
                },
                ensure_ascii=False,
            )

        text = data.get("text", "")

        if _BLOCK_PATTERNS.search(text[:2000]):
            return json.dumps(
                {
                    "ok": False,
                    "blocked": True,
                    "url": url,
                    "text": "",
                    "error": "CAPTCHA_DETECTED",
                    "hint": text[:200],
                    "suggestion": (
                        "该网站有反爬/验证码保护，无法自动抓取。"
                        "可选方案：1) 使用浏览器模式抓取 "
                        "2) 用户手动粘贴正文 3) 搜索其他来源"
                    ),
                },
                ensure_ascii=False,
            )

        stripped_len = len(text.strip())
        if stripped_len < self._min_length:
            return json.dumps(
                {
                    "ok": False,
                    "blocked": True,
                    "url": url,
                    "text": text[:500] if text else "",
                    "error": "CONTENT_TOO_SHORT",
                    "length": stripped_len,
                    "suggestion": (
                        f"获取的内容过短（{stripped_len} 字符），"
                        "可能是反爬页面或空白页。请换用其他来源或由用户提供正文。"
                    ),
                },
                ensure_ascii=False,
            )

        full_length = len(text)
        truncated = full_length > self._max_output
        if truncated:
            text = text[: self._max_output]

        return json.dumps(
            {
                "ok": True,
                "blocked": False,
                "url": url,
                "final_url": data.get("finalUrl", url),
                "text": text,
                "length": full_length,
                "truncated": truncated,
                "extractor": data.get("extractor", "unknown"),
                "error": None,
            },
            ensure_ascii=False,
        )


# ---------------------------------------------------------------------------
# FetchGuard — turn-level execution control
# ---------------------------------------------------------------------------


class FetchGuard:
    """Turn-level guard: tracks fetch attempts and blocks unsourced generation.

    Provides two controls:
    1. ToolAttemptLimiter: per-URL and per-turn fetch attempt caps
    2. NoSourceNoWrite: blocks write_file when fetches were attempted but all failed
    """

    MAX_FETCH_PER_URL = 2
    MAX_FETCH_TOTAL = 5
    MAX_SUCCESSFUL_FETCHES = 2
    MIN_SOURCE_LENGTH = 500

    _FETCH_TOOLS = frozenset({"smart_fetch", "web_fetch"})

    def __init__(self):
        self._url_attempts: dict[str, int] = {}
        self._tool_counts: dict[str, int] = {}
        self._fetch_attempted = False
        self._has_valid_sources = False
        self._successful_count = 0

    def pre_execute(self, tool_name: str, tool_args: dict) -> str | None:
        """Check before tool execution. Returns error string if blocked, None if OK."""

        if tool_name in self._FETCH_TOOLS:
            self._fetch_attempted = True

            if self._successful_count >= self.MAX_SUCCESSFUL_FETCHES:
                return (
                    f"已成功获取 {self._successful_count} 篇文章内容，无需继续抓取。"
                    "请直接基于已有内容生成摘要/简报。"
                )

            url = tool_args.get("url", "")
            self._url_attempts[url] = self._url_attempts.get(url, 0) + 1
            if self._url_attempts[url] > self.MAX_FETCH_PER_URL:
                return (
                    f"ABORT: 已对该 URL 尝试 {self._url_attempts[url] - 1} 次抓取均失败。"
                    "请停止重试，向用户说明无法自动获取该内容。"
                )

        self._tool_counts[tool_name] = self._tool_counts.get(tool_name, 0) + 1

        total_fetch = sum(
            self._tool_counts.get(t, 0) for t in (*self._FETCH_TOOLS, "exec")
        )
        if total_fetch > self.MAX_FETCH_TOTAL:
            return (
                f"ABORT: 本轮已使用 {total_fetch} 次抓取/执行工具，超出上限 {self.MAX_FETCH_TOTAL}。"
                "请停止重试并向用户报告当前结果。"
            )

        if (
            tool_name == "write_file"
            and self._fetch_attempted
            and not self._has_valid_sources
        ):
            return (
                "BLOCKED: 本轮尝试了 URL 抓取但未获取到有效内容，"
                "禁止生成并写入文件。请向用户说明抓取失败，不要编造内容。"
            )

        return None

    def post_execute(self, tool_name: str, tool_args: dict, result: str):
        """Update guard state after tool execution."""
        if tool_name not in self._FETCH_TOOLS:
            return
        try:
            data = json.loads(result)
            if data.get("ok") and len(data.get("text", "")) >= self.MIN_SOURCE_LENGTH:
                self._has_valid_sources = True
                self._successful_count += 1
        except (json.JSONDecodeError, TypeError, AttributeError):
            if isinstance(result, str) and len(result) >= self.MIN_SOURCE_LENGTH:
                self._has_valid_sources = True
                self._successful_count += 1
