"""add project llm prompt language

Revision ID: 20260901_0020
Revises: 20260831_0019
Create Date: 2026-09-01 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260901_0020"
down_revision: str | None = "20260831_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "llm_prompt_language",
            sa.String(length=16),
            nullable=False,
            server_default="zh-CN",
        ),
    )
    op.execute("UPDATE projects SET llm_prompt_language = 'zh-CN' WHERE llm_prompt_language IS NULL")


def downgrade() -> None:
    op.drop_column("projects", "llm_prompt_language")
