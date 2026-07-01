"""Job creation integration tests (Celery dispatch is stubbed in conftest)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _create_device(client, headers, platform="cisco_ios_xe"):
    resp = await client.post(
        "/api/v1/devices",
        json={
            "name": f"dev-{platform}",
            "platform": platform,
            "host": "10.0.0.30",
            "port": 22,
            "transport": "mock",
            "username": "admin",
            "secret": "pw",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _create_config(client, headers, platform="cisco_ios_xe"):
    resp = await client.post(
        "/api/v1/configs",
        json={
            "name": f"cfg-{platform}",
            "platform": platform,
            "format": "cli",
            "content": "hostname x\nend\n",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_start_backup_creates_pending_job(
    client: AsyncClient, operator_headers: dict[str, str]
):
    device_id = await _create_device(client, operator_headers)
    resp = await client.post(
        "/api/v1/jobs/backup",
        json={"device_id": device_id, "name": "nightly-backup"},
        headers=operator_headers,
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["type"] == "backup"
    assert body["status"] == "pending"
    assert body["celery_task_id"]


async def test_apply_compatible_config(
    client: AsyncClient, operator_headers: dict[str, str]
):
    device_id = await _create_device(client, operator_headers)
    config_id = await _create_config(client, operator_headers)
    resp = await client.post(
        "/api/v1/jobs/apply",
        json={"device_id": device_id, "config_file_id": config_id, "dry_run": True},
        headers=operator_headers,
    )
    assert resp.status_code == 202
    assert resp.json()["type"] == "apply"


async def test_apply_incompatible_platform_rejected(
    client: AsyncClient, operator_headers: dict[str, str]
):
    device_id = await _create_device(client, operator_headers, platform="cisco_ios_xe")
    config_id = await _create_config(client, operator_headers, platform="arista_eos")
    resp = await client.post(
        "/api/v1/jobs/apply",
        json={"device_id": device_id, "config_file_id": config_id},
        headers=operator_headers,
    )
    assert resp.status_code == 422
    assert "incompatible" in resp.json()["detail"].lower()


async def test_list_jobs(client: AsyncClient, operator_headers: dict[str, str]):
    device_id = await _create_device(client, operator_headers)
    await client.post(
        "/api/v1/jobs/backup",
        json={"device_id": device_id, "name": "b1"},
        headers=operator_headers,
    )
    resp = await client.get("/api/v1/jobs", headers=operator_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
