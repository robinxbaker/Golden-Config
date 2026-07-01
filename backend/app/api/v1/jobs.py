"""Job endpoints: trigger backup/apply operations and inspect their status."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import CurrentUser, DbSession, require_operator
from app.models import User, UserRole
from app.schemas.job import JobRead
from app.services import audit_service, config_service, device_service, job_service
from app.services.job_service import JobError

router = APIRouter(prefix="/jobs", tags=["jobs"])


class BackupJobRequest(BaseModel):
    device_id: uuid.UUID
    name: str
    description: str | None = None


class ApplyJobRequest(BaseModel):
    device_id: uuid.UUID
    config_file_id: uuid.UUID
    dry_run: bool = False


async def _owned_device_or_404(db: DbSession, device_id: uuid.UUID, user: User):
    device = await device_service.get(db, device_id)
    if not device:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found")
    if device.owner_id != user.id and user.role != UserRole.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your device")
    return device


@router.post(
    "/backup", response_model=JobRead, status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_operator)],
)
async def start_backup(
    db: DbSession, current_user: CurrentUser, payload: BackupJobRequest
) -> JobRead:
    """Capture the device's running configuration into a new config file (async)."""
    device = await _owned_device_or_404(db, payload.device_id, current_user)
    job = await job_service.create_backup_job(db, current_user, device)
    task_id = job_service.dispatch(job, backup_name=payload.name)
    job = await job_service.mark_dispatched(db, job, task_id)
    await audit_service.record(
        db, actor_id=current_user.id, action="job.backup",
        target_type="device", target_id=device.id,
    )
    return JobRead.model_validate(job)


@router.post(
    "/apply", response_model=JobRead, status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_operator)],
)
async def start_apply(
    db: DbSession, current_user: CurrentUser, payload: ApplyJobRequest
) -> JobRead:
    """Apply a compatible config file to the device (async)."""
    device = await _owned_device_or_404(db, payload.device_id, current_user)
    config = await config_service.get(db, payload.config_file_id)
    if not config:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Config file not found")
    if not await config_service.user_has_access(db, current_user, config):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No access to this config file")
    try:
        job = await job_service.create_apply_job(db, current_user, device, config)
    except JobError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    task_id = job_service.dispatch(job, dry_run=payload.dry_run)
    job = await job_service.mark_dispatched(db, job, task_id)
    await audit_service.record(
        db, actor_id=current_user.id, action="job.apply",
        target_type="device", target_id=device.id,
        detail=f"config={config.id} dry_run={payload.dry_run}",
    )
    return JobRead.model_validate(job)


@router.get("", response_model=list[JobRead])
async def list_jobs(db: DbSession, current_user: CurrentUser) -> list[JobRead]:
    jobs = await job_service.list_for_user(db, current_user)
    return [JobRead.model_validate(j) for j in jobs]


@router.get("/{job_id}", response_model=JobRead)
async def get_job(db: DbSession, current_user: CurrentUser, job_id: uuid.UUID) -> JobRead:
    job = await job_service.get(db, job_id)
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    if job.user_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your job")
    return JobRead.model_validate(job)
