"""Share request schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import ShareStatus
from app.schemas.common import ORMModel
from app.schemas.user import UserPublic


class ShareRequestCreate(BaseModel):
    config_file_id: uuid.UUID
    message: str | None = Field(default=None, max_length=512)


class ShareRequestRead(ORMModel):
    id: uuid.UUID
    config_file_id: uuid.UUID
    requester_id: uuid.UUID
    owner_id: uuid.UUID
    status: ShareStatus
    message: str | None = None
    responded_at: datetime | None = None
    created_at: datetime
    requester: UserPublic | None = None


class ShareRequestDecision(BaseModel):
    accept: bool
