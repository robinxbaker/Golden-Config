"""Auth flow integration tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_login_success_and_me(client: AsyncClient, admin_headers: dict[str, str]):
    resp = await client.get("/api/v1/auth/me", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["username"] == "admin_user"
    assert resp.json()["role"] == "admin"


async def test_login_wrong_password(client: AsyncClient, admin_headers: dict[str, str]):
    resp = await client.post(
        "/api/v1/auth/login", data={"username": "admin_user", "password": "nope"}
    )
    assert resp.status_code == 401


async def test_refresh_token(client: AsyncClient, admin_headers: dict[str, str]):
    login = await client.post(
        "/api/v1/auth/login", data={"username": "admin_user", "password": "password123"}
    )
    refresh = login.json()["refresh_token"]
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


async def test_protected_route_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/devices")
    assert resp.status_code == 401


async def test_health_is_public(client: AsyncClient):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
