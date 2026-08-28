"""add project last opened timestamp

Revision ID: 20260825_0017
Revises: 20260824_0016
Create Date: 2026-08-25 14:10:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260825_0017"
down_revision: str | None = "20260824_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("last_opened_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("UPDATE projects SET last_opened_at = created_at WHERE last_opened_at IS NULL")
    op.alter_column(
        "projects",
        "last_opened_at",
        nullable=False,
        server_default=sa.text("now()"),
    )
    op.create_index(op.f("ix_projects_last_opened_at"), "projects", ["last_opened_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_projects_last_opened_at"), table_name="projects")
    op.drop_column("projects", "last_opened_at")
