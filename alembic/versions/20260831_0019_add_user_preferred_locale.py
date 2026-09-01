"""add user preferred locale

Revision ID: 20260831_0019
Revises: 20260825_0018
Create Date: 2026-08-31 23:45:00

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260831_0019"
down_revision: str | None = "20260825_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "preferred_locale",
            sa.String(length=20),
            nullable=False,
            server_default="zh-CN",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "preferred_locale")
