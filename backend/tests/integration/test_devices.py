"""Device inventory integration tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

DEVICE_PAYLOAD = {
    "name": "lab-switch-1",
    "platform": "cisco_ios_xe",
    "vendor": "Cisco",
    "model": "Catalyst 3850",
    "host": "10.0.0.21",
    "port": 22,
    "transport": "mock",
    "username": "admin",
    "secret": "devpass",
}


async def _create_device(client: AsyncClient, headers: dict[str, str]) -> str:
    resp = await client.post("/api/v1/devices", json=DEVICE_PAYLOAD, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_operator_can_create_and_list_devices(
    client: AsyncClient, operator_headers: dict[str, str]
):
    device_id = await _create_device(client, operator_headers)
    resp = await client.get("/api/v1/devices", headers=operator_headers)
    assert resp.status_code == 200
    ids = [d["id"] for d in resp.json()]
    assert device_id in ids
    # Secret must never be returned, only its presence.
    device = next(d for d in resp.json() if d["id"] == device_id)
    assert device["has_secret"] is True
    assert "secret" not in device


async def test_viewer_cannot_create_device(
    client: AsyncClient, viewer_headers: dict[str, str]
):
    resp = await client.post("/api/v1/devices", json=DEVICE_PAYLOAD, headers=viewer_headers)
    assert resp.status_code == 403


async def test_create_rejects_unknown_platform(
    client: AsyncClient, operator_headers: dict[str, str]
):
    payload = {**DEVICE_PAYLOAD, "platform": "nonexistent_os"}
    resp = await client.post("/api/v1/devices", json=payload, headers=operator_headers)
    assert resp.status_code == 422


async def test_connectivity_check_mock_ok(
    client: AsyncClient, operator_headers: dict[str, str]
):
    device_id = await _create_device(client, operator_headers)
    resp = await client.post(f"/api/v1/devices/{device_id}/test", headers=operator_headers)
    assert resp.status_code == 200
    assert resp.json()["reachable"] is True
