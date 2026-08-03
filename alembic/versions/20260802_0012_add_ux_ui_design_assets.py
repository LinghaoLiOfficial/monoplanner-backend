"""add ux and ui design assets

Revision ID: 20260802_0012
Revises: 20260714_0011
Create Date: 2026-08-02 00:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260802_0012"
down_revision: str | None = "20260714_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    _create_design_asset_table("ux_designs")
    _create_design_asset_table("ui_designs")


def downgrade() -> None:
    _drop_design_asset_table("ui_designs")
    _drop_design_asset_table("ux_designs")


def _create_design_asset_table(table_name: str) -> None:
    op.create_table(
        table_name,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("source_requirement_id", sa.Uuid(), nullable=True),
        sa.Column("source_story_id", sa.Uuid(), nullable=True),
        sa.Column("change_set_id", sa.Uuid(), nullable=True),
        sa.Column("generation_run_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("content", json_type, nullable=False, server_default="{}"),
        sa.Column("diff_from_previous", json_type, nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["change_set_id"], ["change_sets.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["generation_run_id"], ["generation_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_requirement_id"], ["requirements.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["source_story_id"], ["business_requirement_stories.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "project_id",
        "source_story_id",
        "change_set_id",
        "generation_run_id",
        "created_at",
    ):
        op.create_index(op.f(f"ix_{table_name}_{column}"), table_name, [column])


def _drop_design_asset_table(table_name: str) -> None:
    for column in (
        "created_at",
        "generation_run_id",
        "change_set_id",
        "source_story_id",
        "project_id",
    ):
        op.drop_index(op.f(f"ix_{table_name}_{column}"), table_name=table_name)
    op.drop_table(table_name)
