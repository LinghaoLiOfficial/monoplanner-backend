"""create structured draft tables

Revision ID: 20260708_0003
Revises: 20260708_0002
Create Date: 2026-07-08 00:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260708_0003"
down_revision: str | None = "20260708_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "api_contract_drafts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("blueprint_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("base_path", sa.String(length=100), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
        sa.ForeignKeyConstraint(["blueprint_id"], ["project_blueprints.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_api_contract_drafts_project_id"), "api_contract_drafts", ["project_id"]
    )
    op.create_index(
        op.f("ix_api_contract_drafts_blueprint_id"), "api_contract_drafts", ["blueprint_id"]
    )
    op.create_index(
        op.f("ix_api_contract_drafts_created_at"), "api_contract_drafts", ["created_at"]
    )

    op.create_table(
        "db_model_drafts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("blueprint_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
        sa.ForeignKeyConstraint(["blueprint_id"], ["project_blueprints.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_db_model_drafts_project_id"), "db_model_drafts", ["project_id"])
    op.create_index(op.f("ix_db_model_drafts_blueprint_id"), "db_model_drafts", ["blueprint_id"])
    op.create_index(op.f("ix_db_model_drafts_created_at"), "db_model_drafts", ["created_at"])

    op.create_table(
        "context_packs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("blueprint_id", sa.Uuid(), nullable=True),
        sa.Column("api_contract_id", sa.Uuid(), nullable=True),
        sa.Column("db_model_id", sa.Uuid(), nullable=True),
        sa.Column("role", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        sa.Column("format", sa.String(length=50), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["api_contract_id"], ["api_contract_drafts.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["blueprint_id"], ["project_blueprints.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["db_model_id"], ["db_model_drafts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_context_packs_project_id"), "context_packs", ["project_id"])
    op.create_index(op.f("ix_context_packs_blueprint_id"), "context_packs", ["blueprint_id"])
    op.create_index(op.f("ix_context_packs_api_contract_id"), "context_packs", ["api_contract_id"])
    op.create_index(op.f("ix_context_packs_db_model_id"), "context_packs", ["db_model_id"])
    op.create_index(op.f("ix_context_packs_role"), "context_packs", ["role"])
    op.create_index(op.f("ix_context_packs_created_at"), "context_packs", ["created_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_context_packs_created_at"), table_name="context_packs")
    op.drop_index(op.f("ix_context_packs_role"), table_name="context_packs")
    op.drop_index(op.f("ix_context_packs_db_model_id"), table_name="context_packs")
    op.drop_index(op.f("ix_context_packs_api_contract_id"), table_name="context_packs")
    op.drop_index(op.f("ix_context_packs_blueprint_id"), table_name="context_packs")
    op.drop_index(op.f("ix_context_packs_project_id"), table_name="context_packs")
    op.drop_table("context_packs")

    op.drop_index(op.f("ix_db_model_drafts_created_at"), table_name="db_model_drafts")
    op.drop_index(op.f("ix_db_model_drafts_blueprint_id"), table_name="db_model_drafts")
    op.drop_index(op.f("ix_db_model_drafts_project_id"), table_name="db_model_drafts")
    op.drop_table("db_model_drafts")

    op.drop_index(op.f("ix_api_contract_drafts_created_at"), table_name="api_contract_drafts")
    op.drop_index(op.f("ix_api_contract_drafts_blueprint_id"), table_name="api_contract_drafts")
    op.drop_index(op.f("ix_api_contract_drafts_project_id"), table_name="api_contract_drafts")
    op.drop_table("api_contract_drafts")
