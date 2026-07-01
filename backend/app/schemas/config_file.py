"""Config file schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import ConfigFormat
from app.schemas.common import ORMModel


class ConfigFileBase(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=512)
    platform: str
    format: ConfigFormat = ConfigFormat.CLI


class ConfigFileCreate(ConfigFileBase):
    content: str


class ConfigFileUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    description: str | None = Field(default=None, max_length=512)
    content: str | None = None


class ConfigFileRead(ORMModel, ConfigFileBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    source_device_id: uuid.UUID | None = None
    version: int
    content: str
    created_at: datetime
    updated_at: datetime


class ConfigFileSummary(ORMModel):
    """Listing view without the (potentially large) content body."""

    id: uuid.UUID
    name: str
    description: str | None = None
    platform: str
    format: ConfigFormat
    version: int
    owner_id: uuid.UUID
    created_at: datetime
