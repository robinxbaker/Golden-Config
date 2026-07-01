"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-01-01 00:00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


user_role = sa.Enum("admin", "operator", "viewer", name="user_role")
transport_type = sa.Enum("mock", "real", name="transport_type")
config_format = sa.Enum("cli", "json", "set", name="config_format")
job_type = sa.Enum("backup", "apply", name="job_type")
job_status = sa.Enum("pending", "running", "succeeded", "failed", name="job_status")
share_status = sa.Enum("pending", "accepted", "denied", name="share_status")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(128), nullable=True),
        sa.Column("role", user_role, nullable=False, server_default="viewer"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("platform", sa.String(64), nullable=False),
        sa.Column("vendor", sa.String(64), nullable=True),
        sa.Column("model", sa.String(64), nullable=True),
        sa.Column("host", sa.String(255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False, server_default="22"),
        sa.Column("transport", transport_type, nullable=False, server_default="mock"),
        sa.Column("username", sa.String(128), nullable=True),
        sa.Column("encrypted_secret", sa.String(512), nullable=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_devices_name", "devices", ["name"])
    op.create_index("ix_devices_platform", "devices", ["platform"])

    op.create_table(
        "config_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.String(512), nullable=True),
        sa.Column("platform", sa.String(64), nullable=False),
        sa.Column("format", config_format, nullable=False, server_default="cli"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_device_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("devices.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_config_files_name", "config_files", ["name"])
    op.create_index("ix_config_files_platform", "config_files", ["platform"])

    op.create_table(
        "config_share_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "config_file_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("config_files.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("config_file_id", "user_id", name="uq_grant_file_user"),
    )

    op.create_table(
        "share_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "config_file_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("config_files.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "requester_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", share_status, nullable=False, server_default="pending"),
        sa.Column("message", sa.String(512), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("type", job_type, nullable=False),
        sa.Column("status", job_status, nullable=False, server_default="pending"),
        sa.Column(
            "device_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("devices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "config_file_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("config_files.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("celery_task_id", sa.String(155), nullable=True),
        sa.Column("log", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_jobs_celery_task_id", "jobs", ["celery_task_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("target_type", sa.String(64), nullable=True),
        sa.Column("target_id", sa.String(64), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("jobs")
    op.drop_table("share_requests")
    op.drop_table("config_share_grants")
    op.drop_table("config_files")
    op.drop_table("devices")
    op.drop_table("users")
    for enum in (job_status, job_type, share_status, config_format, transport_type, user_role):
        enum.drop(op.get_bind(), checkfirst=True)
