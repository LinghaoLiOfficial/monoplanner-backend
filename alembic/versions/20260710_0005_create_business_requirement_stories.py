"""create business requirement stories table

Revision ID: 20260710_0005
Revises: 20260709_0004
Create Date: 2026-07-10 00:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260710_0005"
down_revision: str | None = "20260709_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "business_requirement_stories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("requirement_id", sa.Uuid(), nullable=True),
        sa.Column("generation_run_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("priority", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("user_story", sa.Text(), nullable=False),
        sa.Column("business_scope", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("data_rules", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("acceptance_criteria", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("vertical_slice_note", sa.Text(), nullable=True),
        sa.Column("source_requirement_excerpt", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(["generation_run_id"], ["generation_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requirement_id"], ["requirements.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_business_requirement_stories_project_id"),
        "business_requirement_stories",
        ["project_id"],
    )
    op.create_index(
        op.f("ix_business_requirement_stories_requirement_id"),
        "business_requirement_stories",
        ["requirement_id"],
    )
    op.create_index(
        op.f("ix_business_requirement_stories_generation_run_id"),
        "business_requirement_stories",
        ["generation_run_id"],
    )
    op.create_index(
        op.f("ix_business_requirement_stories_priority"),
        "business_requirement_stories",
        ["priority"],
    )
    op.create_index(
        op.f("ix_business_requirement_stories_status"),
        "business_requirement_stories",
        ["status"],
    )
    op.create_index(
        op.f("ix_business_requirement_stories_created_at"),
        "business_requirement_stories",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_business_requirement_stories_created_at"),
        table_name="business_requirement_stories",
    )
    op.drop_index(
        op.f("ix_business_requirement_stories_status"),
        table_name="business_requirement_stories",
    )
    op.drop_index(
        op.f("ix_business_requirement_stories_priority"),
        table_name="business_requirement_stories",
    )
    op.drop_index(
        op.f("ix_business_requirement_stories_generation_run_id"),
        table_name="business_requirement_stories",
    )
    op.drop_index(
        op.f("ix_business_requirement_stories_requirement_id"),
        table_name="business_requirement_stories",
    )
    op.drop_index(
        op.f("ix_business_requirement_stories_project_id"),
        table_name="business_requirement_stories",
    )
    op.drop_table("business_requirement_stories")
