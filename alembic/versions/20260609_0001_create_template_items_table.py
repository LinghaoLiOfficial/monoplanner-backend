"""create template items table

Revision ID: 20260609_0001
Revises:
Create Date: 2026-06-09 18:45:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260609_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "template_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_template_items_id"), "template_items", ["id"], unique=False)
    op.create_index(op.f("ix_template_items_key"), "template_items", ["key"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_template_items_key"), table_name="template_items")
    op.drop_index(op.f("ix_template_items_id"), table_name="template_items")
    op.drop_table("template_items")
