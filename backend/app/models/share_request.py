"""Share request workflow model (request -> accept/deny)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ShareStatus

if TYPE_CHECKING:
    from app.models.config_file import ConfigFile
    from app.models.user import User


class ShareRequest(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A request from one user to access another user's config file."""

    __tablename__ = "share_requests"

    config_file_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("config_files.id", ondelete="CASCADE"), nullable=False
    )
    requester_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    status: Mapped[ShareStatus] = mapped_column(
        Enum(ShareStatus, name="share_status", values_callable=lambda obj: [e.value for e in obj]),
        default=ShareStatus.PENDING,
        nullable=False,
    )
    message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    config_file: Mapped[ConfigFile] = relationship()
    requester: Mapped[User] = relationship(foreign_keys=[requester_id])
    owner: Mapped[User] = relationship(foreign_keys=[owner_id])
