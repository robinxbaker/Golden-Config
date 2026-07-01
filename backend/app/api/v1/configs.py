"""Config file endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import PlainTextResponse

from app.api.deps import CurrentUser, DbSession
from app.models import ConfigFile, User, UserRole
from app.schemas.config_file import (
    ConfigFileCreate,
    ConfigFileRead,
    ConfigFileSummary,
    ConfigFileUpdate,
)
from app.services import audit_service, config_service

router = APIRouter(prefix="/configs", tags=["configs"])


async def _get_readable_or_404(db: DbSession, config_id: uuid.UUID, user: User) -> ConfigFile:
    config = await config_service.get(db, config_id)
    if not config:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Config file not found")
    if not await config_service.user_has_access(db, user, config):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have access to this config")
    return config


def _require_owner(config: ConfigFile, user: User) -> None:
    if config.owner_id != user.id and user.role != UserRole.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the owner can modify this config")


@router.get("", response_model=list[ConfigFileSummary])
async def list_configs(db: DbSession, current_user: CurrentUser) -> list[ConfigFileSummary]:
    configs = await config_service.list_accessible(db, current_user)
    return [ConfigFileSummary.model_validate(c) for c in configs]


@router.post("", response_model=ConfigFileRead, status_code=status.HTTP_201_CREATED)
async def create_config(
    db: DbSession, current_user: CurrentUser, payload: ConfigFileCreate
) -> ConfigFileRead:
    config = await config_service.create(db, current_user, payload)
    await audit_service.record(
        db, actor_id=current_user.id, action="config.create",
        target_type="config", target_id=config.id,
    )
    return ConfigFileRead.model_validate(config)


@router.get("/{config_id}", response_model=ConfigFileRead)
async def get_config(
    db: DbSession, current_user: CurrentUser, config_id: uuid.UUID
) -> ConfigFileRead:
    config = await _get_readable_or_404(db, config_id, current_user)
    return ConfigFileRead.model_validate(config)


@router.get("/{config_id}/download", response_class=PlainTextResponse)
async def download_config(
    db: DbSession, current_user: CurrentUser, config_id: uuid.UUID
) -> PlainTextResponse:
    config = await _get_readable_or_404(db, config_id, current_user)
    ext = "json" if config.format.value == "json" else "txt"
    filename = f"{config.name.replace(' ', '_')}.{ext}"
    return PlainTextResponse(
        config.content,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.patch("/{config_id}", response_model=ConfigFileRead)
async def update_config(
    db: DbSession, current_user: CurrentUser, config_id: uuid.UUID, payload: ConfigFileUpdate
) -> ConfigFileRead:
    config = await _get_readable_or_404(db, config_id, current_user)
    _require_owner(config, current_user)
    config = await config_service.update(db, config, payload)
    return ConfigFileRead.model_validate(config)


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_config(
    db: DbSession, current_user: CurrentUser, config_id: uuid.UUID
) -> None:
    config = await _get_readable_or_404(db, config_id, current_user)
    _require_owner(config, current_user)
    await config_service.delete(db, config)
    await audit_service.record(
        db, actor_id=current_user.id, action="config.delete",
        target_type="config", target_id=config_id,
    )
