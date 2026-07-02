"""Tests for the Celery task layer (``app.tasks.device_tasks``).

These exercise the async task bodies directly against the SQLite test database (mock driver
transport, no broker/worker), covering the happy path plus the failure guards for missing
devices/configs and driver errors.
"""

from __future__ import annotations

import uuid

import pytest

from app.db.session import AsyncSessionLocal
from app.drivers import DriverError
from app.models import ConfigFile, ConfigFormat, Job, JobStatus, JobType, UserRole
from app.schemas.device import DeviceCreate
from app.schemas.user import UserCreate
from app.services import device_service, user_service
from app.tasks import device_tasks

pytestmark = pytest.mark.asyncio


async def _make_user(username: str = "task_op") -> uuid.UUID:
    async with AsyncSessionLocal() as db:
        user = await user_service.create_user(
            db,
            UserCreate(
                username=username,
                email=f"{username}@example.com",
                password="password123",
                role=UserRole.OPERATOR,
            ),
        )
        return user.id


async def _make_device(owner_id: uuid.UUID, platform: str = "cisco_ios_xe") -> uuid.UUID:
    async with AsyncSessionLocal() as db:
        owner = await user_service.get_by_id(db, owner_id)
        assert owner is not None
        device = await device_service.create(
            db,
            owner,
            DeviceCreate(
                name=f"dev-{platform}",
                platform=platform,
                host="10.0.0.50",
                port=22,
                transport="mock",
                username="admin",
                secret="pw",
            ),
        )
        return device.id


async def _make_config(owner_id: uuid.UUID, platform: str = "cisco_ios_xe") -> uuid.UUID:
    async with AsyncSessionLocal() as db:
        config = ConfigFile(
            name=f"cfg-{platform}",
            platform=platform,
            format=ConfigFormat.CLI,
            content="hostname x\nend\n",
            owner_id=owner_id,
        )
        db.add(config)
        await db.commit()
        await db.refresh(config)
        return config.id


async def _load_job(job_id: uuid.UUID) -> Job:
    async with AsyncSessionLocal() as db:
        job = await db.get(Job, job_id)
        assert job is not None
        return job


async def test_run_backup_succeeds_and_creates_config() -> None:
    user_id = await _make_user()
    device_id = await _make_device(user_id)
    async with AsyncSessionLocal() as db:
        job = Job(type=JobType.BACKUP, device_id=device_id, user_id=user_id)
        db.add(job)
        await db.commit()
        await db.refresh(job)
        job_id = job.id

    await device_tasks._run_backup(str(job_id), "nightly")

    job = await _load_job(job_id)
    assert job.status == JobStatus.SUCCEEDED
    assert job.config_file_id is not None
    assert job.log and "config 'nightly'" in job.log
    assert job.error is None

    async with AsyncSessionLocal() as db:
        config = await db.get(ConfigFile, job.config_file_id)
        assert config is not None
        assert config.name == "nightly"
        assert config.content.strip()
        assert config.source_device_id == device_id


async def test_run_backup_missing_device_marks_failed() -> None:
    user_id = await _make_user("orphan_backup")
    async with AsyncSessionLocal() as db:
        job = Job(type=JobType.BACKUP, device_id=uuid.uuid4(), user_id=user_id)
        db.add(job)
        await db.commit()
        await db.refresh(job)
        job_id = job.id

    await device_tasks._run_backup(str(job_id), "nightly")

    job = await _load_job(job_id)
    assert job.status == JobStatus.FAILED
    assert job.error and "no longer exists" in job.error
    assert job.config_file_id is None


async def test_run_backup_driver_error_marks_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = await _make_user("err_backup")
    device_id = await _make_device(user_id)
    async with AsyncSessionLocal() as db:
        job = Job(type=JobType.BACKUP, device_id=device_id, user_id=user_id)
        db.add(job)
        await db.commit()
        await db.refresh(job)
        job_id = job.id

    def _boom(_target: object) -> object:
        raise DriverError("connection refused")

    monkeypatch.setattr(device_tasks, "get_driver", _boom)

    await device_tasks._run_backup(str(job_id), "nightly")

    job = await _load_job(job_id)
    assert job.status == JobStatus.FAILED
    assert job.error == "connection refused"


async def test_run_apply_succeeds_dry_run() -> None:
    user_id = await _make_user("apply_op")
    device_id = await _make_device(user_id)
    config_id = await _make_config(user_id)
    async with AsyncSessionLocal() as db:
        job = Job(
            type=JobType.APPLY,
            device_id=device_id,
            config_file_id=config_id,
            user_id=user_id,
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        job_id = job.id

    await device_tasks._run_apply(str(job_id), dry_run=True)

    job = await _load_job(job_id)
    assert job.status == JobStatus.SUCCEEDED
    assert job.log
    assert job.error is None


async def test_run_apply_missing_config_marks_failed() -> None:
    user_id = await _make_user("apply_missing")
    device_id = await _make_device(user_id)
    async with AsyncSessionLocal() as db:
        job = Job(
            type=JobType.APPLY,
            device_id=device_id,
            config_file_id=uuid.uuid4(),
            user_id=user_id,
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        job_id = job.id

    await device_tasks._run_apply(str(job_id), dry_run=True)

    job = await _load_job(job_id)
    assert job.status == JobStatus.FAILED
    assert job.error and "no longer exists" in job.error


async def test_load_job_raises_for_unknown_id() -> None:
    with pytest.raises(RuntimeError, match="not found"):
        async with AsyncSessionLocal() as db:
            await device_tasks._load_job(db, str(uuid.uuid4()))


async def test_format_for_returns_config_format() -> None:
    user_id = await _make_user("fmt_op")
    device_id = await _make_device(user_id)
    async with AsyncSessionLocal() as db:
        device = await device_service.get(db, device_id)
        assert device is not None
        fmt = device_tasks._format_for(device)
    assert isinstance(fmt, ConfigFormat)
