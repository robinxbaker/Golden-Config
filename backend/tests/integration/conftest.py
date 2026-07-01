"""Fixtures for integration tests.

These exercise the FastAPI app end-to-end against a SQL database. By default the app uses
PostgreSQL (docker-compose locally or the CI ``postgres`` service); set ``DATABASE_URL`` to
``sqlite+aiosqlite:///./test.db`` to run the suite locally without Docker. Celery dispatch is
stubbed so jobs are created without a running worker/broker.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db.base import Base
from app.db.session import AsyncSessionLocal, engine
from app.main import app
from app.models import UserRole
from app.schemas.user import UserCreate
from app.services import job_service, user_service


@pytest_asyncio.fixture(autouse=True)
async def _schema() -> AsyncGenerator[None, None]:
    """Create a clean schema for every test and tear it down afterwards."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(autouse=True)
def _stub_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Avoid hitting a real Celery broker during tests."""
    monkeypatch.setattr(job_service, "dispatch", lambda *a, **k: f"task-{uuid.uuid4()}")


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _create_user(username: str, role: UserRole) -> None:
    async with AsyncSessionLocal() as db:
        await user_service.create_user(
            db,
            UserCreate(
                username=username,
                email=f"{username}@example.com",
                password="password123",
                role=role,
            ),
        )


async def _login(client: AsyncClient, username: str) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": "password123"},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def admin_headers(client: AsyncClient) -> dict[str, str]:
    await _create_user("admin_user", UserRole.ADMIN)
    return await _login(client, "admin_user")


@pytest_asyncio.fixture
async def operator_headers(client: AsyncClient) -> dict[str, str]:
    await _create_user("operator_user", UserRole.OPERATOR)
    return await _login(client, "operator_user")


@pytest_asyncio.fixture
async def viewer_headers(client: AsyncClient) -> dict[str, str]:
    await _create_user("viewer_user", UserRole.VIEWER)
    return await _login(client, "viewer_user")
