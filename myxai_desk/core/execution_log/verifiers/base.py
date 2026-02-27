"""Base verifier class and global registry for tool result verification."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

log = logging.getLogger("myxai")


class BaseVerifier(ABC):
    """Subclass and register for specific tool names."""

    @abstractmethod
    def tool_names(self) -> list[str]:
        """Return the tool names this verifier handles."""
        ...

    @abstractmethod
    def verify(self, tool_name: str, result: str) -> list[dict]:
        """Run checks and return a list of ``{"name": ..., "pass": bool, "detail": ...}``."""
        ...


VERIFIER_REGISTRY: dict[str, BaseVerifier] = {}


def register_verifier(verifier: BaseVerifier) -> None:
    for name in verifier.tool_names():
        VERIFIER_REGISTRY[name] = verifier


def get_verifier(tool_name: str) -> BaseVerifier | None:
    return VERIFIER_REGISTRY.get(tool_name)


def _auto_register() -> None:
    """Import built-in verifier modules so they self-register."""
    try:
        from myxai_desk.core.execution_log.verifiers import fs as _fs  # noqa: F401
    except Exception:
        pass
    try:
        from myxai_desk.core.execution_log.verifiers import net as _net  # noqa: F401
    except Exception:
        pass


_auto_register()
