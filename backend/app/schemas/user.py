"""User and authentication schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import UserRole
from app.schemas.common import ORMModel


class UserBase(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: EmailStr
    full_name: str | None = Field(default=None, max_length=128)


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.VIEWER


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=128)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    role: UserRole | None = None
    is_active: bool | None = None


class UserRead(ORMModel, UserBase):
    id: uuid.UUID
    role: UserRole
    is_active: bool
    created_at: datetime


class UserPublic(ORMModel):
    """Minimal user info exposed when listing users for sharing."""

    id: uuid.UUID
    username: str
    full_name: str | None = None


# ---- Auth ----


class LoginRequest(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPayload(BaseModel):
    sub: str | None = None
    type: str | None = None
