"""add project target stacks configured flag

Revision ID: 20260712_0010
Revises: 20260712_0009
Create Date: 2026-07-12 00:00:00

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260712_0010"
down_revision: str | None = "20260712_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_FRONTEND_STACK = "Next.js + React + TypeScript + Tailwind CSS 4 + Shadcn/ui + pnpm"
DEFAULT_BACKEND_STACK = (
    "Python 3.12 + FastAPI + Uvicorn + SQLAlchemy 2.x + Alembic + PostgreSQL + uv"
)


def upgrade() -> None:
    bind = op.get_bind()
    op.add_column(
        "projects",
        sa.Column(
            "target_stacks_configured",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    bind.execute(
        sa.text(
            """
            UPDATE projects
            SET target_frontend_stack = :default_frontend
            WHERE trim(coalesce(target_frontend_stack, '')) = ''
            """
        ),
        {"default_frontend": DEFAULT_FRONTEND_STACK},
    )
    bind.execute(
        sa.text(
            """
            UPDATE projects
            SET target_backend_stack = :default_backend
            WHERE trim(coalesce(target_backend_stack, '')) = ''
            """
        ),
        {"default_backend": DEFAULT_BACKEND_STACK},
    )
    bind.execute(
        sa.text(
            """
            UPDATE projects
            SET target_stacks_configured = true
            WHERE trim(target_frontend_stack) <> :default_frontend
               OR trim(target_backend_stack) <> :default_backend
               OR EXISTS (
                    SELECT 1
                    FROM project_blueprints
                    WHERE project_blueprints.project_id = projects.id
               )
            """
        ),
        {
            "default_frontend": DEFAULT_FRONTEND_STACK,
            "default_backend": DEFAULT_BACKEND_STACK,
        },
    )


def downgrade() -> None:
    op.drop_column("projects", "target_stacks_configured")
