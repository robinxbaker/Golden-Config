"""Network device model."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import TransportType

if TYPE_CHECKING:
    from app.models.user import User


class Device(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "devices"

    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    # Driver registry key, e.g. "cisco_ios_xe", "juniper_junos", "arista_eos".
    platform: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    vendor: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)

    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, default=22, nullable=False)
    transport: Mapped[TransportType] = mapped_column(
        Enum(TransportType, name="transport_type", values_callable=lambda obj: [e.value for e in obj]),
        default=TransportType.MOCK,
        nullable=False,
    )

    username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Password / API token, encrypted at rest via app.core.crypto.
    encrypted_secret: Mapped[str | None] = mapped_column(String(512), nullable=True)

    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    owner: Mapped[User] = relationship(back_populates="devices")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Device {self.name} [{self.platform}]>"
