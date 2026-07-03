"""Config file model and the access grants that result from accepted share requests."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ConfigFormat

if TYPE_CHECKING:
    from app.models.user import User


class ConfigFile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A captured configuration that can later be applied to a compatible device."""

    __tablename__ = "config_files"

    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Driver key this config is valid for; gates which devices it can be applied to.
    platform: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    format: Mapped[ConfigFormat] = mapped_column(
        Enum(ConfigFormat, name="config_format", values_callable=lambda obj: [e.value for e in obj]),
        default=ConfigFormat.CLI,
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # Device this config was captured from (nullable for uploaded configs).
    source_device_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("devices.id", ondelete="SET NULL"), nullable=True
    )

    owner: Mapped[User] = relationship(back_populates="config_files")
    grants: Mapped[list[ConfigShareGrant]] = relationship(
        back_populates="config_file", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ConfigFile {self.name} [{self.platform}] v{self.version}>"


class ConfigShareGrant(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Read access to a config file granted to a non-owner via an accepted share."""

    __tablename__ = "config_share_grants"
    __table_args__ = (
        UniqueConstraint("config_file_id", "user_id", name="uq_grant_file_user"),
    )

    config_file_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("config_files.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    config_file: Mapped[ConfigFile] = relationship(back_populates="grants")
