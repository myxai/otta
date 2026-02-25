"""Process execution capability — governance wrapper + standalone fallback.

Architecture note
-----------------
In the normal Agent loop, command execution is performed by **nanobot's
built-in ``run_command`` / ``execute`` tools**.  The governance layer in
``governance.py`` handles post-execution audit.

This module provides a **standalone subprocess runner** used only when:
  - A Prompt App runs outside the nanobot Agent loop (``app_runtime.py``)
  - Direct programmatic command execution is needed (e.g. cron jobs)

It is NOT a replacement for nanobot's command tools.
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import sys
import uuid
from typing import Any


def _new_action_id() -> str:
    return f"act_{uuid.uuid4().hex[:12]}"


def _win_fix_cmd(command: str, args: list[str]) -> tuple[str, list[str]]:
    """On Windows, .cmd/.bat files need ``cmd /c`` wrapping."""
    if sys.platform != "win32":
        return command, args
    exe = shutil.which(command)
    if exe and exe.lower().endswith((".cmd", ".bat")):
        return "cmd", ["/c", command, *args]
    return command, args


class Proc:
    """Standalone subprocess execution (fallback for Prompt App runtime).

    In the Agent loop, nanobot's own command tools are used instead.
    See ``governance.py`` for the post-execution governance hooks.
    """

    def __init__(self, *, undo_registry: Any = None, audit_ledger: Any = None):
        self._undo = undo_registry
        self._audit = audit_ledger

    async def execute(
        self,
        command: str,
        args: list[str] | None = None,
        *,
        cwd: str | None = None,
        timeout: int = 30,
        env: dict[str, str] | None = None,
    ) -> dict:
        """Run *command* with *args* in a subprocess.

        Returns dict with ``stdout``, ``stderr``, ``returncode``, ``action_id``.
        """
        args = args or []
        cmd, fixed_args = _win_fix_cmd(command, args)
        action_id = _new_action_id()

        try:
            proc = await asyncio.create_subprocess_exec(
                cmd, *fixed_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
            )
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(), timeout=timeout,
            )
            stdout = stdout_b.decode("utf-8", errors="replace")[:50_000]
            stderr = stderr_b.decode("utf-8", errors="replace")[:10_000]
        except asyncio.TimeoutError:
            proc.kill()
            stdout, stderr = "", f"Command timed out after {timeout}s"
            returncode = -1
        except Exception as e:
            stdout, stderr = "", str(e)
            returncode = -1
        else:
            returncode = proc.returncode or 0

        result = {
            "stdout": stdout,
            "stderr": stderr,
            "returncode": returncode,
            "action_id": action_id,
        }

        if self._audit:
            self._audit.append_entry(
                capability="proc.execute",
                args={"command": command, "args": args, "cwd": cwd},
                action_id=action_id,
                result_summary=f"exit={returncode}, stdout_len={len(stdout)}",
            )

        return result

    def execute_sync(
        self,
        command: str,
        args: list[str] | None = None,
        *,
        cwd: str | None = None,
        timeout: int = 30,
    ) -> dict:
        """Synchronous wrapper around execute."""
        args = args or []
        cmd, fixed_args = _win_fix_cmd(command, args)
        action_id = _new_action_id()

        try:
            result = subprocess.run(
                [cmd, *fixed_args],
                capture_output=True, text=True,
                timeout=timeout, cwd=cwd,
            )
            stdout = result.stdout[:50_000]
            stderr = result.stderr[:10_000]
            returncode = result.returncode
        except subprocess.TimeoutExpired:
            stdout, stderr = "", f"Command timed out after {timeout}s"
            returncode = -1
        except Exception as e:
            stdout, stderr = "", str(e)
            returncode = -1

        return {
            "stdout": stdout,
            "stderr": stderr,
            "returncode": returncode,
            "action_id": action_id,
        }
