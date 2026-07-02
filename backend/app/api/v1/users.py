"""User management endpoints (admin-managed; self-registration disabled by default)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentUser, DbSession, require_admin
from app.schemas.user import UserCreate, UserPublic, UserRead, UserUpdate
from app.services import audit_service, user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserPublic])
async def list_users(db: DbSession, current_user: CurrentUser) -> list[UserPublic]:
    """List users (minimal public fields) — used for the share-request picker."""
    users = await user_service.list_users(db)
    return [UserPublic.model_validate(u) for u in users]


@router.post(
    "", response_model=UserRead, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
async def create_user(db: DbSession, current_user: CurrentUser, payload: UserCreate) -> UserRead:
    if await user_service.get_by_username(db, payload.username):
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already exists")
    if await user_service.get_by_email(db, payload.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already exists")
    user = await user_service.create_user(db, payload)
    await audit_service.record(
        db, actor_id=current_user.id, action="user.create", target_type="user", target_id=user.id
    )
    return UserRead.model_validate(user)


@router.patch(
    "/{user_id}", response_model=UserRead, dependencies=[Depends(require_admin)]
)
async def update_user(
    db: DbSession, current_user: CurrentUser, user_id: uuid.UUID, payload: UserUpdate
) -> UserRead:
    user = await user_service.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    user = await user_service.update_user(db, user, payload)
    await audit_service.record(
        db, actor_id=current_user.id, action="user.update", target_type="user", target_id=user.id
    )
    return UserRead.model_validate(user)
