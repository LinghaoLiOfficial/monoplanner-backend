"""add generation run progress fields

Revision ID: 20260711_0006
Revises: 20260710_0005
Create Date: 2026-07-11 00:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260711_0006"
down_revision: str | None = "20260710_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("generation_runs", sa.Column("requirement_id", sa.Uuid(), nullable=True))
    op.add_column(
        "generation_runs",
        sa.Column("progress", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("generation_runs", sa.Column("message", sa.Text(), nullable=True))
    op.create_index(
        op.f("ix_generation_runs_requirement_id"),
        "generation_runs",
        ["requirement_id"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("fk_generation_runs_requirement_id_requirements"),
        "generation_runs",
        "requirements",
        ["requirement_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_generation_runs_requirement_id_requirements"),
        "generation_runs",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_generation_runs_requirement_id"), table_name="generation_runs")
    op.drop_column("generation_runs", "message")
    op.drop_column("generation_runs", "progress")
    op.drop_column("generation_runs", "requirement_id")
