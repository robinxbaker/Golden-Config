"""Unit tests for security helpers and credential encryption."""

from __future__ import annotations

import pytest
from jose import JWTError

from app.core.crypto import decrypt_secret, encrypt_secret
from app.core.security import (
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip():
    hashed = hash_password("s3cr3t-password")
    assert hashed != "s3cr3t-password"
    assert verify_password("s3cr3t-password", hashed)
    assert not verify_password("wrong", hashed)


def test_access_token_contains_expected_claims():
    token = create_access_token("user-123", role="admin")
    claims = decode_token(token)
    assert claims["sub"] == "user-123"
    assert claims["type"] == TokenType.ACCESS.value
    assert claims["role"] == "admin"


def test_refresh_token_type():
    claims = decode_token(create_refresh_token("user-123"))
    assert claims["type"] == TokenType.REFRESH.value


def test_decode_rejects_tampered_token():
    token = create_access_token("user-123")
    with pytest.raises(JWTError):
        decode_token(token + "tampered")


def test_credential_encryption_roundtrip():
    cipher = encrypt_secret("device-password")
    assert cipher != "device-password"
    assert decrypt_secret(cipher) == "device-password"


def test_decrypt_invalid_token_raises():
    with pytest.raises(ValueError):
        decrypt_secret("not-a-valid-token")
