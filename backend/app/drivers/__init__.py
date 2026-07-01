"""Pluggable network device drivers.

A *driver* knows how to talk to one family of devices. Every driver supports two
transports:

* ``mock`` — an in-memory simulator that returns realistic sample output. This is the
  default so the whole application runs with no hardware.
* ``real`` — a live connection (SSH via Netmiko/NAPALM, or REST via httpx).

Drivers self-register with the :data:`registry` at import time, so adding support for a
new platform is just a matter of dropping in a new subclass.
"""

from app.drivers.base import BaseDriver, DeviceTarget, DriverError
from app.drivers.registry import (
    DriverMeta,
    get_driver,
    get_driver_class,
    list_drivers,
    registry,
)

# Import driver modules for their registration side effects.
from app.drivers import rest_drivers, ssh_drivers  # noqa: E402,F401

__all__ = [
    "BaseDriver",
    "DeviceTarget",
    "DriverError",
    "DriverMeta",
    "get_driver",
    "get_driver_class",
    "list_drivers",
    "registry",
]
