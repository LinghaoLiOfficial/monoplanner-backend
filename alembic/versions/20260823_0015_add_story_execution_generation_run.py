"""add execution generation run to business requirement stories

Revision ID: 20260823_0015
Revises: 20260814_0014
Create Date: 2026-08-23 00:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260823_0015"
down_revision: str | None = "20260814_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "business_requirement_stories",
        sa.Column("execution_generation_run_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_business_requirement_stories_execution_generation_run_id",
        "business_requirement_stories",
        "generation_runs",
        ["execution_generation_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_business_requirement_stories_execution_generation_run_id"),
        "business_requirement_stories",
        ["execution_generation_run_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_business_requirement_stories_execution_generation_run_id"),
        table_name="business_requirement_stories",
    )
    op.drop_constraint(
        "fk_business_requirement_stories_execution_generation_run_id",
        "business_requirement_stories",
        type_="foreignkey",
    )
    op.drop_column("business_requirement_stories", "execution_generation_run_id")
