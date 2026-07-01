"""Job service: create backup/apply jobs and dispatch them to Celery."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ConfigFile, Device, Job, JobStatus, JobType, User, UserRole


class JobError(Exception):
    """Raised on invalid job creation (e.g. platform mismatch)."""


async def get(db: AsyncSession, job_id: uuid.UUID) -> Job | None:
    return await db.get(Job, job_id)


async def list_for_user(db: AsyncSession, user: User, limit: int = 100) -> list[Job]:
    stmt = select(Job).order_by(Job.created_at.desc()).limit(limit)
    if user.role != UserRole.ADMIN:
        stmt = stmt.where(Job.user_id == user.id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_backup_job(db: AsyncSession, user: User, device: Device) -> Job:
    job = Job(type=JobType.BACKUP, device_id=device.id, user_id=user.id)
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def create_apply_job(
    db: AsyncSession, user: User, device: Device, config: ConfigFile
) -> Job:
    if config.platform != device.platform:
        raise JobError(
            f"Config platform '{config.platform}' is incompatible with device "
            f"platform '{device.platform}'."
        )
    job = Job(
        type=JobType.APPLY,
        device_id=device.id,
        config_file_id=config.id,
        user_id=user.id,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


def dispatch(job: Job, *, backup_name: str | None = None, dry_run: bool = False) -> str:
    """Send a job to Celery and return the task id. Imported lazily to avoid cycles."""
    from app.tasks import device_tasks

    if job.type == JobType.BACKUP:
        async_result = device_tasks.run_backup.delay(str(job.id), backup_name or "backup")
    else:
        async_result = device_tasks.run_apply.delay(str(job.id), dry_run)
    return async_result.id


async def mark_dispatched(db: AsyncSession, job: Job, task_id: str) -> Job:
    job.celery_task_id = task_id
    job.status = JobStatus.PENDING
    await db.commit()
    await db.refresh(job)
    return job
