"""Secrets manager — system keyring with encrypted file fallback.

Stores sensitive values (API keys, passwords) outside of plain-text
config files.  Priority:

    1. System keyring via ``keyring`` library (Windows Credential Locker,
       macOS Keychain, Linux SecretService/KWallet).
    2. Encrypted local file (``~/.nanobot/policy/.secrets.enc``) using a
       machine-local key derived from :func:`_derive_machine_key`.

Public API
----------
    store(name, value)       — persist a secret
    retrieve(name)           — read a secret (or None)
    delete(name)             — remove a secret
    clear_all()              — wipe every secret in our namespace
    list_keys()              — return stored key names
    backend_info()           — which backend is active + health
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import platform
import uuid
from pathlib import Path
from typing import Any

from myxai_desk.core.storage.paths import NANOBOT_HOME, POLICY_DIR, ensure_dir

log = logging.getLogger("myxai.secrets")

_SERVICE_NAME = "myxai-desk"
_SECRETS_FILE = POLICY_DIR / ".secrets.enc"
_KEY_FILE = POLICY_DIR / ".machine_key"

# ── Backend selection ──────────────────────────────────────────────────

try:
    import keyring as _kr
    # Quick health check — some Linux installs have keyring but no backend
    _kr.get_password(_SERVICE_NAME, "__probe__")
    _BACKEND = "keyring"
except Exception:
    _kr = None  # type: ignore[assignment]
    _BACKEND = "file"


def backend_info() -> dict[str, Any]:
    """Return which backend is active and its health status."""
    return {
        "backend": _BACKEND,
        "keyring_available": _kr is not None,
        "keyring_backend": str(getattr(_kr, "get_keyring", lambda: None)()) if _kr else None,
        "file_path": str(_SECRETS_FILE) if _BACKEND == "file" else None,
    }


# ── Machine-local key derivation ──────────────────────────────────────

def _derive_machine_key() -> bytes:
    """Derive a 32-byte encryption key unique to this machine + OS user.

    The key is deterministic (no random salt) so we can decrypt on each
    run without asking the user for a password.  It is *not* a substitute
    for a proper master-password vault, but it prevents plain-text secrets
    on disk and makes casual exfiltration of the file useless without the
    same machine context.
    """
    # Mix machine id + username + home path
    parts = [
        platform.node(),
        str(Path.home()),
        str(NANOBOT_HOME),
    ]
    try:
        parts.append(str(uuid.getnode()))
    except Exception:
        pass

    raw = "|".join(parts).encode()
    return hashlib.sha256(raw).digest()


# ── Encrypted-file backend ─────────────────────────────────────────────

def _xor_bytes(data: bytes, key: bytes) -> bytes:
    """XOR *data* with repeating *key* (simple but sufficient for local
    machine-bound encryption)."""
    out = bytearray(len(data))
    klen = len(key)
    for i, b in enumerate(data):
        out[i] = b ^ key[i % klen]
    return bytes(out)


def _load_file_store() -> dict[str, str]:
    if not _SECRETS_FILE.exists():
        return {}
    try:
        enc = _SECRETS_FILE.read_bytes()
        key = _derive_machine_key()
        raw = _xor_bytes(enc, key)
        return json.loads(raw)
    except Exception:
        log.warning("Failed to read secrets file — may be corrupted or from another machine")
        return {}


def _save_file_store(store: dict[str, str]) -> None:
    ensure_dir(POLICY_DIR)
    key = _derive_machine_key()
    raw = json.dumps(store, ensure_ascii=False).encode()
    enc = _xor_bytes(raw, key)
    _SECRETS_FILE.write_bytes(enc)


# ── Public API ─────────────────────────────────────────────────────────

def store(name: str, value: str) -> None:
    """Persist a secret *value* under *name*."""
    if not value:
        delete(name)
        return
    if _BACKEND == "keyring" and _kr is not None:
        try:
            _kr.set_password(_SERVICE_NAME, name, value)
            return
        except Exception:
            log.warning("keyring store failed for %s, falling back to file", name)
    s = _load_file_store()
    s[name] = value
    _save_file_store(s)


def retrieve(name: str) -> str | None:
    """Read a secret. Returns None if not found."""
    if _BACKEND == "keyring" and _kr is not None:
        try:
            val = _kr.get_password(_SERVICE_NAME, name)
            if val is not None:
                return val
        except Exception:
            log.debug("keyring retrieve failed for %s, trying file", name)
    s = _load_file_store()
    return s.get(name)


def delete(name: str) -> None:
    """Remove a secret."""
    if _BACKEND == "keyring" and _kr is not None:
        try:
            _kr.delete_password(_SERVICE_NAME, name)
        except Exception:
            pass
    s = _load_file_store()
    if name in s:
        del s[name]
        _save_file_store(s)


def clear_all() -> None:
    """Wipe every secret we manage."""
    # File store
    if _SECRETS_FILE.exists():
        _SECRETS_FILE.unlink(missing_ok=True)
    # Keyring — we track known keys in the file store to enumerate them
    if _BACKEND == "keyring" and _kr is not None:
        for name in list_keys():
            try:
                _kr.delete_password(_SERVICE_NAME, name)
            except Exception:
                pass
    log.info("[secrets] all secrets cleared")


def list_keys() -> list[str]:
    """Return names of stored secrets (from file store index)."""
    return list(_load_file_store().keys())


# ── Config-level helpers ───────────────────────────────────────────────
#
# Conventions:
#   provider API key  → "provider.<name>.api_key"  (e.g. "provider.openrouter.api_key")
#   search API key    → "search.<name>.api_key"
#   email password    → "app.email_summary.imap_password"
#   MCP header tokens → "mcp.<server>.headers"

PROVIDER_KEY_PREFIX = "provider."
SEARCH_KEY_PREFIX = "search."
APP_KEY_PREFIX = "app."
MCP_KEY_PREFIX = "mcp."

# Placeholder written into config JSON when secret is in keyring
SECRET_REF = "<<KEYRING>>"


def is_secret_ref(value: str | None) -> bool:
    """Check if a config value is a keyring reference placeholder."""
    return value == SECRET_REF


def store_provider_key(provider_name: str, api_key: str) -> None:
    store(f"{PROVIDER_KEY_PREFIX}{provider_name}.api_key", api_key)


def retrieve_provider_key(provider_name: str) -> str | None:
    return retrieve(f"{PROVIDER_KEY_PREFIX}{provider_name}.api_key")


def store_search_key(provider_name: str, api_key: str) -> None:
    store(f"{SEARCH_KEY_PREFIX}{provider_name}.api_key", api_key)


def retrieve_search_key(provider_name: str) -> str | None:
    return retrieve(f"{SEARCH_KEY_PREFIX}{provider_name}.api_key")


def store_app_secret(app_id: str, field: str, value: str) -> None:
    store(f"{APP_KEY_PREFIX}{app_id}.{field}", value)


def retrieve_app_secret(app_id: str, field: str) -> str | None:
    return retrieve(f"{APP_KEY_PREFIX}{app_id}.{field}")
