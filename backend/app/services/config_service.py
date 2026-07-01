"""Config file service: CRUD plus access control via ownership and share grants."""

from __future__ import annotations

import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ConfigFile, ConfigShareGrant, User, UserRole
from app.schemas.config_file import ConfigFileCreate, ConfigFileUpdate


async def get(db: AsyncSession, config_id: uuid.UUID) -> ConfigFile | None:
    return await db.get(ConfigFile, config_id)


async def user_has_access(db: AsyncSession, user: User, config: ConfigFile) -> bool:
    """A user can read a config if admin, owner, or holds a share grant."""
    if user.role == UserRole.ADMIN or config.owner_id == user.id:
        return True
    result = await db.execute(
        select(ConfigShareGrant.id).where(
            ConfigShareGrant.config_file_id == config.id,
            ConfigShareGrant.user_id == user.id,
        )
    )
    return result.scalar_one_or_none() is not None


async def list_accessible(db: AsyncSession, user: User) -> list[ConfigFile]:
    """Return configs the user owns or has been granted access to (admins: all)."""
    if user.role == UserRole.ADMIN:
        result = await db.execute(select(ConfigFile).order_by(ConfigFile.name))
        return list(result.scalars().all())

    granted_subq = select(ConfigShareGrant.config_file_id).where(
        ConfigShareGrant.user_id == user.id
    )
    result = await db.execute(
        select(ConfigFile)
        .where(or_(ConfigFile.owner_id == user.id, ConfigFile.id.in_(granted_subq)))
        .order_by(ConfigFile.name)
    )
    return list(result.scalars().all())


async def create(
    db: AsyncSession,
    owner: User,
    payload: ConfigFileCreate,
    *,
    source_device_id: uuid.UUID | None = None,
) -> ConfigFile:
    config = ConfigFile(
        name=payload.name,
        description=payload.description,
        platform=payload.platform,
        format=payload.format,
        content=payload.content,
        owner_id=owner.id,
        source_device_id=source_device_id,
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return config


async def update(db: AsyncSession, config: ConfigFile, payload: ConfigFileUpdate) -> ConfigFile:
    data = payload.model_dump(exclude_unset=True)
    if data.get("content") is not None and data["content"] != config.content:
        config.version += 1
    for field, value in data.items():
        setattr(config, field, value)
    await db.commit()
    await db.refresh(config)
    return config


async def delete(db: AsyncSession, config: ConfigFile) -> None:
    await db.delete(config)
    await db.commit()
