"""Share request workflow: request access, then owner accepts or denies."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import ConfigFile, ConfigShareGrant, ShareRequest, ShareStatus, User


class ShareError(Exception):
    """Raised on invalid share operations (duplicate, self-share, etc.)."""


async def create_request(
    db: AsyncSession, requester: User, config: ConfigFile, message: str | None
) -> ShareRequest:
    if config.owner_id == requester.id:
        raise ShareError("You already own this config file.")

    existing = await db.execute(
        select(ShareRequest).where(
            ShareRequest.config_file_id == config.id,
            ShareRequest.requester_id == requester.id,
            ShareRequest.status == ShareStatus.PENDING,
        )
    )
    if existing.scalar_one_or_none():
        raise ShareError("You already have a pending request for this config file.")

    # Already has access?
    grant = await db.execute(
        select(ConfigShareGrant.id).where(
            ConfigShareGrant.config_file_id == config.id,
            ConfigShareGrant.user_id == requester.id,
        )
    )
    if grant.scalar_one_or_none():
        raise ShareError("You already have access to this config file.")

    request = ShareRequest(
        config_file_id=config.id,
        requester_id=requester.id,
        owner_id=config.owner_id,
        message=message,
    )
    db.add(request)
    await db.commit()
    return await _load_with_requester(db, request.id)


async def _load_with_requester(db: AsyncSession, request_id: uuid.UUID) -> ShareRequest:
    """Re-fetch a request with its ``requester`` eagerly loaded for serialization."""
    result = await db.execute(
        select(ShareRequest)
        .options(selectinload(ShareRequest.requester))
        .where(ShareRequest.id == request_id)
    )
    return result.scalar_one()


async def get(db: AsyncSession, request_id: uuid.UUID) -> ShareRequest | None:
    return await db.get(ShareRequest, request_id)


async def list_incoming(db: AsyncSession, owner: User) -> list[ShareRequest]:
    """Requests awaiting this user's decision (they own the config files)."""
    result = await db.execute(
        select(ShareRequest)
        .options(selectinload(ShareRequest.requester))
        .where(ShareRequest.owner_id == owner.id)
        .order_by(ShareRequest.created_at.desc())
    )
    return list(result.scalars().all())


async def list_outgoing(db: AsyncSession, requester: User) -> list[ShareRequest]:
    """Requests this user has made for others' config files."""
    result = await db.execute(
        select(ShareRequest)
        .options(selectinload(ShareRequest.requester))
        .where(ShareRequest.requester_id == requester.id)
        .order_by(ShareRequest.created_at.desc())
    )
    return list(result.scalars().all())


async def decide(db: AsyncSession, request: ShareRequest, *, accept: bool) -> ShareRequest:
    if request.status != ShareStatus.PENDING:
        raise ShareError("This request has already been answered.")

    request.status = ShareStatus.ACCEPTED if accept else ShareStatus.DENIED
    request.responded_at = datetime.now(UTC)

    if accept:
        db.add(
            ConfigShareGrant(
                config_file_id=request.config_file_id,
                user_id=request.requester_id,
            )
        )
    await db.commit()
    return await _load_with_requester(db, request.id)
