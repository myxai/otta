"""Sandbox / workspace isolation for Prompt App execution.

For now, this is a lightweight "restricted subprocess + workspace fence"
implementation.  Container-based isolation can be added later.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from myxai_desk.core.storage.paths import NANOBOT_HOME, ensure_dir


class Sandbox:
    """Workspace-scoped execution sandbox for a Prompt App."""

    def __init__(self, app_id: str, *, workspace: str | Path | None = None):
        self.app_id = app_id
        if workspace:
            self.workspace = Path(workspace)
        else:
            self.workspace = NANOBOT_HOME / "sandboxes" / app_id
        ensure_dir(self.workspace)

    @property
    def root(self) -> Path:
        return self.workspace

    def is_path_allowed(self, path: str | Path) -> bool:
        """Check if *path* is within the sandbox workspace."""
        try:
            resolved = Path(path).resolve()
            return self.workspace.resolve() in resolved.parents or resolved == self.workspace.resolve()
        except (OSError, ValueError):
            return False

    def make_env(self, base_env: dict[str, str] | None = None) -> dict[str, str]:
        """Create a restricted environment for subprocess execution."""
        env = dict(base_env or os.environ)
        env["MYXAI_SANDBOX"] = "1"
        env["MYXAI_APP_ID"] = self.app_id
        env["MYXAI_WORKSPACE"] = str(self.workspace)
        # Remove potentially dangerous env vars for third-party apps
        for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
                     "GITHUB_TOKEN", "OPENAI_API_KEY"):
            env.pop(key, None)
        return env

    def cleanup(self) -> None:
        """Remove temporary sandbox files (keeps workspace intact)."""
        pass  # Workspace persists; only temp files are cleaned
