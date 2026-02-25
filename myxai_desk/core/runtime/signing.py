"""App package signing and verification.

Official Prompt Apps are signed with an HMAC-SHA256 digest over the
``app.yaml`` and ``prompt.md`` contents.  This provides tamper detection
(not cryptographic non-repudiation — that would require asymmetric keys
and is a future upgrade).

Signing workflow:
    1. Developer runs ``sign_package(pkg_dir, secret)``
    2. A ``.signature`` file is written into the package directory
    3. At load time, ``verify_package(pkg_dir, secret)`` returns True/False

The shared secret is stored in ``~/.nanobot/policy/signing_key``.
If no key exists, one is auto-generated on first use.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import TYPE_CHECKING

from myxai_desk.core.storage.paths import POLICY_DIR, ensure_dir

if TYPE_CHECKING:
    from pathlib import Path

_KEY_FILE = POLICY_DIR / "signing_key"
_SIG_FILENAME = ".signature"


def _get_or_create_key() -> bytes:
    ensure_dir(POLICY_DIR)
    if _KEY_FILE.exists():
        return _KEY_FILE.read_bytes().strip()
    key = secrets.token_hex(32).encode("utf-8")
    _KEY_FILE.write_bytes(key)
    return key


def _package_digest(pkg_dir: Path) -> str:
    """Compute a deterministic digest of the signable files in *pkg_dir*."""
    h = hashlib.sha256()
    for fname in ("app.yaml", "prompt.md"):
        fp = pkg_dir / fname
        if fp.exists():
            h.update(fname.encode("utf-8"))
            h.update(fp.read_bytes())
    return h.hexdigest()


def sign_package(pkg_dir: Path, secret: bytes | None = None) -> str:
    """Sign a Prompt App package.  Returns the hex signature."""
    key = secret or _get_or_create_key()
    digest = _package_digest(pkg_dir)
    sig = hmac.new(key, digest.encode("utf-8"), hashlib.sha256).hexdigest()
    (pkg_dir / _SIG_FILENAME).write_text(sig, encoding="utf-8")
    return sig


def verify_package(pkg_dir: Path, secret: bytes | None = None) -> bool:
    """Verify the signature of a Prompt App package."""
    sig_file = pkg_dir / _SIG_FILENAME
    if not sig_file.exists():
        return False
    key = secret or _get_or_create_key()
    stored_sig = sig_file.read_text(encoding="utf-8").strip()
    digest = _package_digest(pkg_dir)
    expected = hmac.new(key, digest.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(stored_sig, expected)


def is_signed(pkg_dir: Path) -> bool:
    """Check if a package has a signature file (doesn't verify)."""
    return (pkg_dir / _SIG_FILENAME).exists()
