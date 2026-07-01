"""Idempotent seed script: bootstrap admin user and demo inventory.

Run via ``python -m app.initial_data`` (the docker entrypoint does this automatically
after migrations).
"""

from __future__ import annotations

import asyncio

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.session import AsyncSessionLocal
from app.drivers import get_driver
from app.models import ConfigFormat, TransportType, UserRole
from app.schemas.config_file import ConfigFileCreate
from app.schemas.device import DeviceCreate
from app.schemas.user import UserCreate
from app.services import config_service, device_service, user_service

logger = get_logger(__name__)

DEMO_DEVICES = [
    ("core-sw-3850", "cisco_ios_xe", "Cisco", "Catalyst 3850", "10.0.0.11"),
    ("access-sw-2960", "cisco_ios", "Cisco", "Catalyst 2960", "10.0.0.12"),
    ("dc-leaf-arista", "arista_eos", "Arista", "7050X", "10.0.0.13"),
    ("edge-juniper", "juniper_junos", "Juniper", "EX4300", "10.0.0.14"),
    ("wlc-9800", "cisco_9800_wlc", "Cisco", "C9800-40", "10.0.0.15"),
    ("mist-controller", "juniper_mist", "Juniper", "Mist Cloud", "mist.local"),
]


async def seed() -> None:
    configure_logging()
    async with AsyncSessionLocal() as db:
        admin = await user_service.get_by_username(db, settings.FIRST_ADMIN_USERNAME)
        if admin is None:
            admin = await user_service.create_user(
                db,
                UserCreate(
                    username=settings.FIRST_ADMIN_USERNAME,
                    email=settings.FIRST_ADMIN_EMAIL,
                    password=settings.FIRST_ADMIN_PASSWORD,
                    full_name="Platform Administrator",
                    role=UserRole.ADMIN,
                ),
            )
            logger.info("seeded_admin", username=admin.username)
        else:
            logger.info("admin_exists", username=admin.username)

        existing = await device_service.list_for_user(db, admin)
        existing_names = {d.name for d in existing}
        for name, platform, vendor, model, host in DEMO_DEVICES:
            if name in existing_names:
                continue
            device = await device_service.create(
                db,
                admin,
                DeviceCreate(
                    name=name,
                    platform=platform,
                    vendor=vendor,
                    model=model,
                    host=host,
                    port=443 if platform == "juniper_mist" else 22,
                    transport=TransportType.MOCK,
                    username="admin",
                    secret="demo-password",
                ),
            )
            logger.info("seeded_device", name=device.name)

            # Pre-capture a golden config for the first switch so the demo has data.
            if platform == "cisco_ios_xe":
                target = device_service.build_target(device)
                content = get_driver(target).backup()
                await config_service.create(
                    db,
                    admin,
                    ConfigFileCreate(
                        name=f"{name}-golden",
                        description="Seed golden configuration",
                        platform=platform,
                        format=ConfigFormat.CLI,
                        content=content,
                    ),
                    source_device_id=device.id,
                )
                logger.info("seeded_config", device=device.name)


if __name__ == "__main__":
    asyncio.run(seed())
