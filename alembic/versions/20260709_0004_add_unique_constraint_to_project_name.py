"""add unique constraint to project name

Revision ID: 20260709_0004
Revises: 20260708_0003
Create Date: 2026-07-09 00:00:00

"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260709_0004"
down_revision: str | None = "20260708_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint("uq_projects_name", "projects", ["name"])


def downgrade() -> None:
    op.drop_constraint("uq_projects_name", "projects", type_="unique")
