"""Enumerations shared across models and schemas."""

from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    """Role-based access control levels (most to least privileged)."""

    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class TransportType(StrEnum):
    """How the backend reaches a device."""

    MOCK = "mock"  # in-memory simulator; default, needs no hardware
    REAL = "real"  # live SSH / REST to physical or virtual gear


class ConfigFormat(StrEnum):
    """Stored representation of a captured configuration."""

    CLI = "cli"  # raw running-config text
    JSON = "json"  # structured/normalised config
    SET = "set"  # Junos-style `set` commands


class JobType(StrEnum):
    BACKUP = "backup"  # capture running-config -> config file
    APPLY = "apply"  # push a config file -> device


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ShareStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DENIED = "denied"
