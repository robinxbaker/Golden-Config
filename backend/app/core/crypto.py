"""Symmetric encryption for device credentials stored at rest.

Device passwords must be usable by the worker to open SSH sessions, so they cannot be
one-way hashed. Instead we encrypt them with Fernet (AES-128-CBC + HMAC) using a key
provided via ``CREDENTIAL_ENCRYPTION_KEY``.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _build_fernet() -> Fernet:
    key = settings.CREDENTIAL_ENCRYPTION_KEY
    if not key:
        # Derive a deterministic dev key from SECRET_KEY so local runs work without
        # extra setup. Production MUST set CREDENTIAL_ENCRYPTION_KEY explicitly.
        digest = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
        key = base64.urlsafe_b64encode(digest).decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


_fernet = _build_fernet()


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a secret and return a URL-safe token string."""
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt_secret(token: str) -> str:
    """Decrypt a token produced by :func:`encrypt_secret`."""
    try:
        return _fernet.decrypt(token.encode()).decode()
    except InvalidToken as exc:  # pragma: no cover - defensive
        raise ValueError("Unable to decrypt stored credential") from exc


__all__ = ["encrypt_secret", "decrypt_secret"]
