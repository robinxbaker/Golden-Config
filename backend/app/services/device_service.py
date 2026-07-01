"""Device CRUD service and driver-target construction."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt_secret, encrypt_secret
from app.drivers import DeviceTarget
from app.models import Device, User
from app.schemas.device import DeviceCreate, DeviceUpdate


async def get(db: AsyncSession, device_id: uuid.UUID) -> Device | None:
    return await db.get(Device, device_id)


async def list_for_user(db: AsyncSession, user: User) -> list[Device]:
    """Admins see all devices; everyone else sees only their own."""
    stmt = select(Device).order_by(Device.name)
    if user.role != "admin":
        stmt = stmt.where(Device.owner_id == user.id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create(db: AsyncSession, owner: User, payload: DeviceCreate) -> Device:
    device = Device(
        name=payload.name,
        platform=payload.platform,
        vendor=payload.vendor,
        model=payload.model,
        host=payload.host,
        port=payload.port,
        transport=payload.transport,
        username=payload.username,
        encrypted_secret=encrypt_secret(payload.secret) if payload.secret else None,
        owner_id=owner.id,
    )
    db.add(device)
    await db.commit()
    await db.refresh(device)
    return device


async def update(db: AsyncSession, device: Device, payload: DeviceUpdate) -> Device:
    data = payload.model_dump(exclude_unset=True)
    if "secret" in data:
        secret = data.pop("secret")
        device.encrypted_secret = encrypt_secret(secret) if secret else None
    for field, value in data.items():
        setattr(device, field, value)
    await db.commit()
    await db.refresh(device)
    return device


async def delete(db: AsyncSession, device: Device) -> None:
    await db.delete(device)
    await db.commit()


def build_target(device: Device) -> DeviceTarget:
    """Construct a driver :class:`DeviceTarget`, decrypting the stored secret."""
    secret = decrypt_secret(device.encrypted_secret) if device.encrypted_secret else None
    return DeviceTarget(
        platform=device.platform,
        host=device.host,
        port=device.port,
        username=device.username,
        password=secret,
        transport=device.transport.value,
    )
