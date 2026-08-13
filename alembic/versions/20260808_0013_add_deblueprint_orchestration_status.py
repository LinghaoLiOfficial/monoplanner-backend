"""add de-blueprint orchestration status fields

Revision ID: 20260808_0013
Revises: 20260802_0012
Create Date: 2026-08-08 12:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260808_0013"
down_revision: str | None = "20260802_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "requirements",
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
    )
    op.add_column("requirements", sa.Column("applied_at", sa.DateTime(timezone=True)))
    op.create_index(op.f("ix_requirements_status"), "requirements", ["status"], unique=False)

    op.add_column(
        "business_requirement_stories",
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index(
        op.f("ix_business_requirement_stories_is_current"),
        "business_requirement_stories",
        ["is_current"],
        unique=False,
    )

    op.add_column("change_sets", sa.Column("layer", sa.String(length=100)))
    op.add_column("change_sets", sa.Column("batch_id", postgresql.UUID(as_uuid=True)))
    op.add_column("change_sets", sa.Column("applied_at", sa.DateTime(timezone=True)))
    op.add_column(
        "change_sets",
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index(op.f("ix_change_sets_layer"), "change_sets", ["layer"], unique=False)
    op.create_index(op.f("ix_change_sets_batch_id"), "change_sets", ["batch_id"], unique=False)
    op.create_index(
        op.f("ix_change_sets_is_current"), "change_sets", ["is_current"], unique=False
    )

    op.alter_column("api_contract_drafts", "blueprint_id", nullable=True)
    op.alter_column("db_model_drafts", "blueprint_id", nullable=True)


def downgrade() -> None:
    op.alter_column("db_model_drafts", "blueprint_id", nullable=False)
    op.alter_column("api_contract_drafts", "blueprint_id", nullable=False)

    op.drop_index(op.f("ix_change_sets_is_current"), table_name="change_sets")
    op.drop_index(op.f("ix_change_sets_batch_id"), table_name="change_sets")
    op.drop_index(op.f("ix_change_sets_layer"), table_name="change_sets")
    op.drop_column("change_sets", "is_current")
    op.drop_column("change_sets", "applied_at")
    op.drop_column("change_sets", "batch_id")
    op.drop_column("change_sets", "layer")

    op.drop_index(
        op.f("ix_business_requirement_stories_is_current"),
        table_name="business_requirement_stories",
    )
    op.drop_column("business_requirement_stories", "is_current")

    op.drop_index(op.f("ix_requirements_status"), table_name="requirements")
    op.drop_column("requirements", "applied_at")
    op.drop_column("requirements", "status")
