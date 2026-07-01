"""User account model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import UserRole

if TYPE_CHECKING:
    from app.models.config_file import ConfigFile
    from app.models.device import Device


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), default=UserRole.VIEWER, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    devices: Mapped[list["Device"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )
    config_files: Mapped[list["ConfigFile"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.username} ({self.role})>"
