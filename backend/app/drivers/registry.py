"""Driver registry: maps platform keys to driver classes.

Drivers register themselves with :func:`register` (typically via the ``@register``
decorator). Services and the API look drivers up by platform key.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.drivers.base import BaseDriver, DeviceTarget

registry: dict[str, type[BaseDriver]] = {}


@dataclass(frozen=True, slots=True)
class DriverMeta:
    """Lightweight, serialisable description of a driver for the API/UI."""

    platform: str
    display_name: str
    vendor: str
    transport_kind: str
    default_port: int
    config_format: str


def register(cls: type[BaseDriver]) -> type[BaseDriver]:
    """Class decorator that registers a driver under its ``platform`` key."""
    if not getattr(cls, "platform", None):
        raise ValueError(f"{cls.__name__} must define a 'platform' class attribute")
    if cls.platform in registry:
        raise ValueError(f"Duplicate driver platform key: {cls.platform}")
    registry[cls.platform] = cls
    return cls


def get_driver_class(platform: str) -> type[BaseDriver]:
    try:
        return registry[platform]
    except KeyError as exc:
        raise KeyError(f"No driver registered for platform '{platform}'") from exc


def get_driver(target: DeviceTarget) -> BaseDriver:
    """Instantiate the driver for the given target."""
    return get_driver_class(target.platform)(target)


def list_drivers() -> list[DriverMeta]:
    """Return metadata for all registered drivers, sorted by display name."""
    metas = [
        DriverMeta(
            platform=cls.platform,
            display_name=cls.display_name,
            vendor=cls.vendor,
            transport_kind=cls.transport_kind,
            default_port=cls.default_port,
            config_format=cls.config_format,
        )
        for cls in registry.values()
    ]
    return sorted(metas, key=lambda m: m.display_name)
