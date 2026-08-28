"""normalize change set title suffix

Revision ID: 20260825_0018
Revises: 20260825_0017
Create Date: 2026-08-25 23:18:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260825_0018"
down_revision: str | None = "20260825_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE change_sets
        SET title = regexp_replace(btrim(title), '(变更集)+$', '') || '变更集'
        WHERE title IS NOT NULL
        """
    )


def downgrade() -> None:
    # Data normalization is intentionally irreversible.
    pass
