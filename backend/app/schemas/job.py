"""Job schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import JobStatus, JobType
from app.schemas.common import ORMModel


class BackupRequest(BaseModel):
    """Capture a device's running config into a new config file."""

    name: str
    description: str | None = None


class ApplyRequest(BaseModel):
    """Apply an existing config file to a device."""

    config_file_id: uuid.UUID
    dry_run: bool = False


class JobRead(ORMModel):
    id: uuid.UUID
    type: JobType
    status: JobStatus
    device_id: uuid.UUID
    config_file_id: uuid.UUID | None = None
    user_id: uuid.UUID
    celery_task_id: str | None = None
    log: str | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime
