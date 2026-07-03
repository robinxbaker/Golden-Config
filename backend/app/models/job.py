"""Background job model: tracks backup/apply operations run by Celery."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import JobStatus, JobType

if TYPE_CHECKING:
    from app.models.config_file import ConfigFile
    from app.models.device import Device
    from app.models.user import User


class Job(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "jobs"

    type: Mapped[JobType] = mapped_column(
        Enum(JobType, name="job_type", values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status", values_callable=lambda obj: [e.value for e in obj]),
        default=JobStatus.PENDING,
        nullable=False,
    )

    device_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    config_file_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("config_files.id", ondelete="SET NULL"), nullable=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    celery_task_id: Mapped[str | None] = mapped_column(String(155), nullable=True, index=True)
    log: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    device: Mapped[Device] = relationship()
    config_file: Mapped[ConfigFile | None] = relationship()
    user: Mapped[User] = relationship()
