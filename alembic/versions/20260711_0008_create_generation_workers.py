"""create generation workers table

Revision ID: 20260711_0008
Revises: 20260711_0007
Create Date: 2026-07-11 17:05:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260711_0008"
down_revision: str | None = "20260711_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "generation_workers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("worker_id", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column(
            "last_heartbeat_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("worker_id"),
    )
    op.create_index(
        op.f("ix_generation_workers_worker_id"),
        "generation_workers",
        ["worker_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_generation_workers_worker_id"), table_name="generation_workers")
    op.drop_table("generation_workers")
