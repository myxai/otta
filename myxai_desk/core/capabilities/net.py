"""Network / HTTP capability — domain-controlled HTTP requests.

Separated from search: search is a controlled aggregation, net is general HTTP.
Domain allowlist enforcement and exfiltration control are handled by policy
rules; this module only performs the actual HTTP operations.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any
from urllib.parse import urlparse

log = logging.getLogger("myxai.core.capabilities.net")


def _new_action_id() -> str:
    return f"act_{uuid.uuid4().hex[:12]}"


class Net:
    """General-purpose HTTP capability."""

    def __init__(self, *, audit_ledger: Any = None):
        self._audit = audit_ledger

    async def http_get(self, url: str, *, headers: dict | None = None, timeout: int = 30) -> dict:
        import aiohttp  # optional dependency

        action_id = _new_action_id()
        try:
            async with (
                aiohttp.ClientSession() as session,
                session.get(
                    url, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)
                ) as resp,
            ):
                body = await resp.text()
                result = {
                    "status": resp.status,
                    "body": body[:100_000],
                    "headers": dict(resp.headers),
                    "action_id": action_id,
                }
        except ImportError:
            import urllib.request

            req = urllib.request.Request(url, headers=headers or {})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")[:100_000]
                result = {
                    "status": resp.status,
                    "body": body,
                    "action_id": action_id,
                }
        except Exception as e:
            log.warning("HTTP GET failed for %s: %s", url, e, exc_info=True)
            result = {"error": str(e), "action_id": action_id}

        self._log(url, "GET", action_id)
        return result

    async def http_post(
        self,
        url: str,
        *,
        data: str | dict | None = None,
        headers: dict | None = None,
        timeout: int = 30,
    ) -> dict:
        import json
        import urllib.request

        action_id = _new_action_id()
        try:
            body_bytes = (
                json.dumps(data).encode("utf-8")
                if isinstance(data, dict)
                else (data or "").encode("utf-8")
            )
            hdrs = headers or {}
            if isinstance(data, dict):
                hdrs.setdefault("Content-Type", "application/json")
            req = urllib.request.Request(url, data=body_bytes, headers=hdrs, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp_body = resp.read().decode("utf-8", errors="replace")[:100_000]
                result = {
                    "status": resp.status,
                    "body": resp_body,
                    "action_id": action_id,
                }
        except Exception as e:
            log.warning("HTTP POST failed for %s: %s", url, e, exc_info=True)
            result = {"error": str(e), "action_id": action_id}

        self._log(url, "POST", action_id)
        return result

    async def download(self, url: str, dest: str, *, timeout: int = 60) -> dict:
        import urllib.request
        from pathlib import Path

        action_id = _new_action_id()
        try:
            dest_path = Path(dest)
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(url, str(dest_path))
            result = {
                "path": str(dest_path),
                "size": dest_path.stat().st_size,
                "action_id": action_id,
            }
        except Exception as e:
            log.warning("Download failed for %s: %s", url, e, exc_info=True)
            result = {"error": str(e), "action_id": action_id}

        self._log(url, "DOWNLOAD", action_id)
        return result

    def _log(self, url: str, method: str, action_id: str) -> None:
        if self._audit:
            domain = urlparse(url).hostname or "unknown"
            self._audit.append_entry(
                capability=f"net.{method.lower()}",
                args={"url": url, "domain": domain},
                action_id=action_id,
            )
