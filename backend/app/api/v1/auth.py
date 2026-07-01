"""Authentication endpoints: login, refresh, current user."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import CurrentUser, DbSession
from app.core.security import (
    JWTError,
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.schemas.user import RefreshRequest, Token, UserRead
from app.services import audit_service, user_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
async def login(
    db: DbSession,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    """Exchange username/password for an access + refresh token pair."""
    user = await user_service.authenticate(db, form_data.username, form_data.password)
    if not user:
        await audit_service.record(
            db, actor_id=None, action="login.failed", detail=form_data.username
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    await audit_service.record(db, actor_id=user.id, action="login.success")
    return Token(
        access_token=create_access_token(user.id, role=user.role.value),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=Token)
async def refresh(db: DbSession, payload: RefreshRequest) -> Token:
    """Issue a new access token from a valid refresh token."""
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
    )
    try:
        claims = decode_token(payload.refresh_token)
        if claims.get("type") != TokenType.REFRESH.value:
            raise invalid
        user = await user_service.get_by_id(db, uuid.UUID(claims["sub"]))
    except (JWTError, KeyError, ValueError) as exc:
        raise invalid from exc
    if user is None or not user.is_active:
        raise invalid
    return Token(
        access_token=create_access_token(user.id, role=user.role.value),
        refresh_token=create_refresh_token(user.id),
    )


@router.get("/me", response_model=UserRead)
async def read_me(current_user: CurrentUser) -> UserRead:
    return UserRead.model_validate(current_user)
