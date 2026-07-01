"""Device schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import TransportType
from app.schemas.common import ORMModel


class DeviceBase(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    platform: str = Field(description="Driver registry key, e.g. 'cisco_ios_xe'")
    vendor: str | None = None
    model: str | None = None
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=22, ge=1, le=65535)
    transport: TransportType = TransportType.MOCK


class DeviceCreate(DeviceBase):
    username: str | None = None
    # Plaintext on the way in; encrypted before persistence, never returned.
    secret: str | None = Field(default=None, repr=False)


class DeviceUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    vendor: str | None = None
    model: str | None = None
    host: str | None = Field(default=None, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    transport: TransportType | None = None
    username: str | None = None
    secret: str | None = Field(default=None, repr=False)


class DeviceRead(ORMModel, DeviceBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    username: str | None = None
    has_secret: bool = False
    created_at: datetime
    updated_at: datetime


class DeviceConnectivity(BaseModel):
    reachable: bool
    detail: str
