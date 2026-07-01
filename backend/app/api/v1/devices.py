"""Device inventory endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentUser, DbSession, require_operator
from app.drivers import DriverError, get_driver
from app.drivers.registry import registry
from app.models import Device, User, UserRole
from app.schemas.device import (
    DeviceConnectivity,
    DeviceCreate,
    DeviceRead,
    DeviceUpdate,
)
from app.services import audit_service, device_service

router = APIRouter(prefix="/devices", tags=["devices"])


def _to_read(device: Device) -> DeviceRead:
    data = DeviceRead.model_validate(device)
    data.has_secret = device.encrypted_secret is not None
    return data


async def _get_owned_or_404(db: DbSession, device_id: uuid.UUID, user: User) -> Device:
    device = await device_service.get(db, device_id)
    if not device:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found")
    if device.owner_id != user.id and user.role != UserRole.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your device")
    return device


@router.get("", response_model=list[DeviceRead])
async def list_devices(db: DbSession, current_user: CurrentUser) -> list[DeviceRead]:
    devices = await device_service.list_for_user(db, current_user)
    return [_to_read(d) for d in devices]


@router.post(
    "", response_model=DeviceRead, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_operator)],
)
async def create_device(
    db: DbSession, current_user: CurrentUser, payload: DeviceCreate
) -> DeviceRead:
    if payload.platform not in registry:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown platform")
    device = await device_service.create(db, current_user, payload)
    await audit_service.record(
        db, actor_id=current_user.id, action="device.create",
        target_type="device", target_id=device.id,
    )
    return _to_read(device)


@router.get("/{device_id}", response_model=DeviceRead)
async def get_device(
    db: DbSession, current_user: CurrentUser, device_id: uuid.UUID
) -> DeviceRead:
    device = await _get_owned_or_404(db, device_id, current_user)
    return _to_read(device)


@router.patch(
    "/{device_id}", response_model=DeviceRead, dependencies=[Depends(require_operator)]
)
async def update_device(
    db: DbSession, current_user: CurrentUser, device_id: uuid.UUID, payload: DeviceUpdate
) -> DeviceRead:
    device = await _get_owned_or_404(db, device_id, current_user)
    device = await device_service.update(db, device, payload)
    return _to_read(device)


@router.delete(
    "/{device_id}", status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_operator)],
)
async def delete_device(
    db: DbSession, current_user: CurrentUser, device_id: uuid.UUID
) -> None:
    device = await _get_owned_or_404(db, device_id, current_user)
    await device_service.delete(db, device)
    await audit_service.record(
        db, actor_id=current_user.id, action="device.delete",
        target_type="device", target_id=device_id,
    )


@router.post("/{device_id}/test", response_model=DeviceConnectivity)
async def test_connectivity(
    db: DbSession, current_user: CurrentUser, device_id: uuid.UUID
) -> DeviceConnectivity:
    """Run a lightweight reachability check using the device's driver."""
    device = await _get_owned_or_404(db, device_id, current_user)
    target = device_service.build_target(device)
    try:
        reachable = get_driver(target).test_connection()
        return DeviceConnectivity(reachable=reachable, detail="Connection OK")
    except DriverError as exc:
        return DeviceConnectivity(reachable=False, detail=str(exc))
