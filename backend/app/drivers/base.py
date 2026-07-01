"""Base driver abstractions shared by all device drivers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar


class DriverError(RuntimeError):
    """Raised when a driver operation fails (connect, backup, apply)."""


@dataclass(slots=True)
class DeviceTarget:
    """Connection details for a single device, passed to a driver instance."""

    platform: str
    host: str
    port: int
    username: str | None
    password: str | None
    transport: str  # "mock" or "real"


@dataclass(slots=True)
class ApplyResult:
    """Outcome of applying a config to a device."""

    diff: str
    applied: bool
    log: str


class BaseDriver(ABC):
    """Abstract base for all device drivers.

    Concrete subclasses declare class-level metadata and implement the ``_real_*``
    methods. Transport routing (mock vs. real) is handled here so subclasses never
    repeat that logic.
    """

    # ---- Class-level metadata (override in subclasses) ----
    platform: ClassVar[str]
    display_name: ClassVar[str]
    vendor: ClassVar[str]
    transport_kind: ClassVar[str]  # "ssh" or "rest"
    default_port: ClassVar[int] = 22
    config_format: ClassVar[str] = "cli"

    def __init__(self, target: DeviceTarget) -> None:
        self.target = target

    # ---- Public API (transport-aware) ----

    def test_connection(self) -> bool:
        if self.target.transport == "mock":
            return True
        return self._real_test_connection()

    def backup(self) -> str:
        """Return the device's current configuration as text."""
        if self.target.transport == "mock":
            return self.sample_config()
        return self._real_backup()

    def apply(self, config: str, dry_run: bool = False) -> ApplyResult:
        """Push ``config`` to the device (or simulate when mocked / dry-run)."""
        if self.target.transport == "mock":
            return self._mock_apply(config, dry_run)
        return self._real_apply(config, dry_run)

    # ---- Mock behaviour ----

    @abstractmethod
    def sample_config(self) -> str:
        """Return a realistic sample running-config for the mock transport."""

    def _mock_apply(self, config: str, dry_run: bool) -> ApplyResult:
        line_count = len([ln for ln in config.splitlines() if ln.strip()])
        verb = "Would apply" if dry_run else "Applied"
        diff = "\n".join(f"+ {ln}" for ln in config.splitlines() if ln.strip())
        log = (
            f"[mock:{self.platform}] {verb} {line_count} configuration lines to "
            f"{self.target.host}."
        )
        return ApplyResult(diff=diff, applied=not dry_run, log=log)

    # ---- Real behaviour (override in transport mixins) ----

    def _real_test_connection(self) -> bool:  # pragma: no cover - requires hardware
        raise NotImplementedError

    def _real_backup(self) -> str:  # pragma: no cover - requires hardware
        raise NotImplementedError

    def _real_apply(self, config: str, dry_run: bool) -> ApplyResult:  # pragma: no cover
        raise NotImplementedError
