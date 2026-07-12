"""add users and project ownership

Revision ID: 20260712_0009
Revises: 20260711_0008
Create Date: 2026-07-12 00:00:00

"""

from __future__ import annotations

import os
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

import bcrypt
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260712_0009"
down_revision: str | None = "20260711_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MANAGEABLE_ROLES = ("user", "vip-plus", "vip-pro", "vip-pro-max")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=True),
        sa.Column("role", sa.String(length=30), nullable=False, server_default="user"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("avatar_seed", sa.String(length=100), nullable=False),
        sa.Column("avatar_bg_color", sa.String(length=20), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)
    op.create_index(op.f("ix_users_role"), "users", ["role"], unique=False)

    op.create_table(
        "email_verification_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("code_hash", sa.String(length=255), nullable=False),
        sa.Column("purpose", sa.String(length=50), nullable=False, server_default="register"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        op.f("ix_email_verification_codes_email"),
        "email_verification_codes",
        ["email"],
        unique=False,
    )
    op.create_index(
        op.f("ix_email_verification_codes_purpose"),
        "email_verification_codes",
        ["purpose"],
        unique=False,
    )

    bind = op.get_bind()
    admin_id = _ensure_bootstrap_admin(bind)

    op.add_column(
        "projects",
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE projects SET owner_user_id = :admin_id WHERE owner_user_id IS NULL"
        ).bindparams(sa.bindparam("admin_id", admin_id, type_=postgresql.UUID(as_uuid=True)))
    )
    op.alter_column("projects", "owner_user_id", nullable=False)
    op.create_index(op.f("ix_projects_owner_user_id"), "projects", ["owner_user_id"], unique=False)
    op.create_foreign_key(
        "fk_projects_owner_user_id_users",
        "projects",
        "users",
        ["owner_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint("uq_projects_name", "projects", type_="unique")
    op.create_unique_constraint("uq_projects_owner_name", "projects", ["owner_user_id", "name"])


def downgrade() -> None:
    op.drop_constraint("uq_projects_owner_name", "projects", type_="unique")
    op.create_unique_constraint("uq_projects_name", "projects", ["name"])
    op.drop_constraint("fk_projects_owner_user_id_users", "projects", type_="foreignkey")
    op.drop_index(op.f("ix_projects_owner_user_id"), table_name="projects")
    op.drop_column("projects", "owner_user_id")
    op.drop_index(
        op.f("ix_email_verification_codes_purpose"), table_name="email_verification_codes"
    )
    op.drop_index(op.f("ix_email_verification_codes_email"), table_name="email_verification_codes")
    op.drop_table("email_verification_codes")
    op.drop_index(op.f("ix_users_role"), table_name="users")
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")


def _ensure_bootstrap_admin(bind) -> UUID:
    email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "admin@example.com").strip().lower()
    username = os.getenv("BOOTSTRAP_ADMIN_USERNAME", "admin").strip()
    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "Admin123!")
    existing = bind.execute(
        sa.text("SELECT id FROM users WHERE email = :email"), {"email": email}
    ).scalar()
    if existing:
        return existing
    admin_id = uuid4()
    now = datetime.now(UTC)
    bind.execute(
        sa.text(
            """
            INSERT INTO users (
                id, email, username, password_hash, display_name, role, is_active,
                is_email_verified, avatar_seed, avatar_bg_color, created_at, updated_at
            )
            VALUES (
                :id, :email, :username, :password_hash, :display_name, 'admin', true,
                true, :avatar_seed, :avatar_bg_color, :created_at, :updated_at
            )
            """
        ).bindparams(sa.bindparam("id", type_=postgresql.UUID(as_uuid=True))),
        {
            "id": admin_id,
            "email": email,
            "username": username,
            "password_hash": bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
            "display_name": "Administrator",
            "avatar_seed": username[:1].upper() or "A",
            "avatar_bg_color": "#111827",
            "created_at": now,
            "updated_at": now,
        },
    )
    return admin_id
