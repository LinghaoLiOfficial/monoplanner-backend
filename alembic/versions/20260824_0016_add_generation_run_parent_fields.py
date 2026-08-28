"""add parent and asset layer fields to generation runs

Revision ID: 20260824_0016
Revises: 20260823_0015
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260824_0016"
down_revision: str | None = "20260823_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("generation_runs", sa.Column("parent_run_id", sa.Uuid(), nullable=True))
    op.add_column("generation_runs", sa.Column("asset_layer", sa.String(length=100), nullable=True))
    op.create_foreign_key(
        "fk_generation_runs_parent_run_id",
        "generation_runs",
        "generation_runs",
        ["parent_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_generation_runs_parent_run_id", "generation_runs", ["parent_run_id"])
    op.create_index("ix_generation_runs_asset_layer", "generation_runs", ["asset_layer"])


def downgrade() -> None:
    op.drop_index("ix_generation_runs_asset_layer", table_name="generation_runs")
    op.drop_index("ix_generation_runs_parent_run_id", table_name="generation_runs")
    op.drop_constraint("fk_generation_runs_parent_run_id", "generation_runs", type_="foreignkey")
    op.drop_column("generation_runs", "asset_layer")
    op.drop_column("generation_runs", "parent_run_id")
