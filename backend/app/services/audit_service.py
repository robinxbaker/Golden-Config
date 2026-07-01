"""Audit logging service: append security-relevant events."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


async def record(
    db: AsyncSession,
    *,
    actor_id: uuid.UUID | None,
    action: str,
    target_type: str | None = None,
    target_id: str | uuid.UUID | None = None,
    detail: str | None = None,
    commit: bool = True,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        detail=detail,
    )
    db.add(entry)
    if commit:
        await db.commit()
    return entry


async def list_recent(db: AsyncSession, limit: int = 100) -> list[AuditLog]:
    result = await db.execute(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())
