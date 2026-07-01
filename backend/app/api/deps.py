"""Shared API dependencies: DB session, current user, and role guards."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import JWTError, TokenType, decode_token
from app.db.session import get_db
from app.models import User, UserRole
from app.services import user_service

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/login")

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    db: DbSession,
    token: Annotated[str, Depends(oauth2_scheme)],
) -> User:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        if payload.get("type") != TokenType.ACCESS.value:
            raise credentials_exc
        user_id = payload.get("sub")
        if not user_id:
            raise credentials_exc
    except JWTError as exc:
        raise credentials_exc from exc

    import uuid

    try:
        user = await user_service.get_by_id(db, uuid.UUID(user_id))
    except ValueError as exc:
        raise credentials_exc from exc
    if user is None or not user.is_active:
        raise credentials_exc
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: UserRole) -> Callable[[User], Coroutine[Any, Any, User]]:
    """Dependency factory enforcing that the current user has one of ``roles``."""

    async def _guard(current_user: CurrentUser) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for this action.",
            )
        return current_user

    return _guard


# Common guards.
require_admin = require_role(UserRole.ADMIN)
require_operator = require_role(UserRole.ADMIN, UserRole.OPERATOR)
