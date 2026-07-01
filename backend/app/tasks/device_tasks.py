"""Celery tasks that talk to network devices through the driver layer.

Tasks are synchronous from Celery's point of view but use ``asyncio.run`` to reuse the
application's async SQLAlchemy session and services.
"""

from __future__ import annotations

import asyncio
import uuid

from app.core.logging import get_logger
from app.db.session import AsyncSessionLocal
from app.drivers import DriverError, get_driver
from app.models import ConfigFile, Job, JobStatus
from app.services import device_service
from app.worker import celery_app

logger = get_logger(__name__)


async def _load_job(db, job_id: str) -> Job:
    job = await db.get(Job, uuid.UUID(job_id))
    if job is None:
        raise RuntimeError(f"Job {job_id} not found")
    return job


async def _run_backup(job_id: str, name: str) -> None:
    async with AsyncSessionLocal() as db:
        job = await _load_job(db, job_id)
        job.status = JobStatus.RUNNING
        await db.commit()

        device = await device_service.get(db, job.device_id)
        try:
            target = device_service.build_target(device)
            content = get_driver(target).backup()

            config = ConfigFile(
                name=name,
                description=f"Captured from {device.name} ({device.platform})",
                platform=device.platform,
                format=_format_for(device),
                content=content,
                owner_id=job.user_id,
                source_device_id=device.id,
            )
            db.add(config)
            await db.flush()

            job.config_file_id = config.id
            job.status = JobStatus.SUCCEEDED
            job.log = f"Captured {len(content.splitlines())} lines into config '{name}'."
            await db.commit()
            logger.info("backup_succeeded", job_id=job_id, device=str(device.id))
        except DriverError as exc:
            job.status = JobStatus.FAILED
            job.error = str(exc)
            await db.commit()
            logger.warning("backup_failed", job_id=job_id, error=str(exc))


async def _run_apply(job_id: str, dry_run: bool) -> None:
    async with AsyncSessionLocal() as db:
        job = await _load_job(db, job_id)
        job.status = JobStatus.RUNNING
        await db.commit()

        device = await device_service.get(db, job.device_id)
        config = await db.get(ConfigFile, job.config_file_id)
        try:
            target = device_service.build_target(device)
            result = get_driver(target).apply(config.content, dry_run=dry_run)
            job.status = JobStatus.SUCCEEDED
            job.log = f"{result.log}\n\n--- diff ---\n{result.diff}".strip()
            await db.commit()
            logger.info("apply_succeeded", job_id=job_id, dry_run=dry_run)
        except DriverError as exc:
            job.status = JobStatus.FAILED
            job.error = str(exc)
            await db.commit()
            logger.warning("apply_failed", job_id=job_id, error=str(exc))


def _format_for(device) -> str:
    """Pick the stored config format based on the device's driver metadata."""
    from app.drivers.registry import get_driver_class

    from app.models import ConfigFormat

    return ConfigFormat(get_driver_class(device.platform).config_format)


@celery_app.task(name="device.backup")
def run_backup(job_id: str, name: str) -> None:
    asyncio.run(_run_backup(job_id, name))


@celery_app.task(name="device.apply")
def run_apply(job_id: str, dry_run: bool = False) -> None:
    asyncio.run(_run_apply(job_id, dry_run))
