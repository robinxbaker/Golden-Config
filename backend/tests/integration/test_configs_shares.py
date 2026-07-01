"""Config file + share-request workflow integration tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

CONFIG_PAYLOAD = {
    "name": "golden-3850",
    "description": "Golden config for access switches",
    "platform": "cisco_ios_xe",
    "format": "cli",
    "content": "hostname golden\nvlan 10\n name USERS\nend\n",
}


async def _create_config(client: AsyncClient, headers: dict[str, str]) -> str:
    resp = await client.post("/api/v1/configs", json=CONFIG_PAYLOAD, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_owner_can_crud_config(client: AsyncClient, operator_headers: dict[str, str]):
    config_id = await _create_config(client, operator_headers)

    get_resp = await client.get(f"/api/v1/configs/{config_id}", headers=operator_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["version"] == 1

    patch = await client.patch(
        f"/api/v1/configs/{config_id}",
        json={"content": "hostname golden\nvlan 20\nend\n"},
        headers=operator_headers,
    )
    assert patch.status_code == 200
    assert patch.json()["version"] == 2  # content change bumps version


async def test_download_config(client: AsyncClient, operator_headers: dict[str, str]):
    config_id = await _create_config(client, operator_headers)
    resp = await client.get(
        f"/api/v1/configs/{config_id}/download", headers=operator_headers
    )
    assert resp.status_code == 200
    assert "hostname golden" in resp.text
    assert "attachment" in resp.headers["content-disposition"]


async def test_share_request_accept_grants_access(
    client: AsyncClient,
    operator_headers: dict[str, str],
    viewer_headers: dict[str, str],
):
    config_id = await _create_config(client, operator_headers)

    # Viewer cannot see it yet.
    denied = await client.get(f"/api/v1/configs/{config_id}", headers=viewer_headers)
    assert denied.status_code == 403

    # Viewer requests access.
    req = await client.post(
        "/api/v1/shares",
        json={"config_file_id": config_id, "message": "please share"},
        headers=viewer_headers,
    )
    assert req.status_code == 201
    request_id = req.json()["id"]

    # Owner sees it in incoming and accepts.
    incoming = await client.get("/api/v1/shares/incoming", headers=operator_headers)
    assert any(r["id"] == request_id for r in incoming.json())

    decide = await client.post(
        f"/api/v1/shares/{request_id}/decision",
        json={"accept": True},
        headers=operator_headers,
    )
    assert decide.status_code == 200
    assert decide.json()["status"] == "accepted"

    # Viewer can now read it.
    allowed = await client.get(f"/api/v1/configs/{config_id}", headers=viewer_headers)
    assert allowed.status_code == 200


async def test_share_request_deny_keeps_access_closed(
    client: AsyncClient,
    operator_headers: dict[str, str],
    viewer_headers: dict[str, str],
):
    config_id = await _create_config(client, operator_headers)
    req = await client.post(
        "/api/v1/shares",
        json={"config_file_id": config_id},
        headers=viewer_headers,
    )
    request_id = req.json()["id"]
    decide = await client.post(
        f"/api/v1/shares/{request_id}/decision",
        json={"accept": False},
        headers=operator_headers,
    )
    assert decide.json()["status"] == "denied"
    still_denied = await client.get(f"/api/v1/configs/{config_id}", headers=viewer_headers)
    assert still_denied.status_code == 403


async def test_non_owner_cannot_decide(
    client: AsyncClient,
    operator_headers: dict[str, str],
    viewer_headers: dict[str, str],
):
    config_id = await _create_config(client, operator_headers)
    req = await client.post(
        "/api/v1/shares", json={"config_file_id": config_id}, headers=viewer_headers
    )
    request_id = req.json()["id"]
    # Requester tries to accept their own request -> forbidden.
    resp = await client.post(
        f"/api/v1/shares/{request_id}/decision",
        json={"accept": True},
        headers=viewer_headers,
    )
    assert resp.status_code == 403
