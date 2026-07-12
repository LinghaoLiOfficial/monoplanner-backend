"""add generation queue fields

Revision ID: 20260711_0007
Revises: 20260711_0006
Create Date: 2026-07-11 16:20:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260711_0007"
down_revision: str | None = "20260711_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "generation_runs",
        sa.Column(
            "queue_payload",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=True,
        ),
    )
    op.add_column("generation_runs", sa.Column("locked_by", sa.String(length=100), nullable=True))
    op.add_column(
        "generation_runs",
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "generation_runs",
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
    )
    op.add_column(
        "generation_runs",
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "generation_runs",
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "generation_runs",
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "generation_runs",
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "generation_runs", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index(
        "ix_generation_runs_queue_claim",
        "generation_runs",
        ["status", "next_attempt_at", "created_at"],
        unique=False,
    )
    op.create_index(op.f("ix_generation_runs_locked_at"), "generation_runs", ["locked_at"])
    op.create_index(op.f("ix_generation_runs_locked_by"), "generation_runs", ["locked_by"])
    op.create_index(
        op.f("ix_generation_runs_next_attempt_at"),
        "generation_runs",
        ["next_attempt_at"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_generation_runs_next_attempt_at"), table_name="generation_runs")
    op.drop_index(op.f("ix_generation_runs_locked_by"), table_name="generation_runs")
    op.drop_index(op.f("ix_generation_runs_locked_at"), table_name="generation_runs")
    op.drop_index("ix_generation_runs_queue_claim", table_name="generation_runs")
    op.drop_column("generation_runs", "cancelled_at")
    op.drop_column("generation_runs", "next_attempt_at")
    op.drop_column("generation_runs", "locked_at")
    op.drop_column("generation_runs", "started_at")
    op.drop_column("generation_runs", "queued_at")
    op.drop_column("generation_runs", "max_attempts")
    op.drop_column("generation_runs", "attempt_count")
    op.drop_column("generation_runs", "locked_by")
    op.drop_column("generation_runs", "queue_payload")
