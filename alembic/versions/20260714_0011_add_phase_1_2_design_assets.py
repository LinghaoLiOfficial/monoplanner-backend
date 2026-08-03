"""add phase 1-2 design assets

Revision ID: 20260714_0011
Revises: 20260712_0010
Create Date: 2026-07-14 00:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260714_0011"
down_revision: str | None = "20260712_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    _add_project_config_fields()
    _add_business_story_fields()
    _create_change_sets()
    _add_asset_fields("project_blueprints")
    _add_asset_fields("api_contract_drafts")
    _add_asset_fields("db_model_drafts")
    _add_context_pack_asset_fields()
    _create_design_asset_table("frontend_page_structures")
    _create_design_asset_table("frontend_toolings")
    _create_design_asset_table("backend_service_designs")
    _create_design_asset_table("backend_toolings")


def downgrade() -> None:
    _drop_design_asset_table("backend_toolings")
    _drop_design_asset_table("backend_service_designs")
    _drop_design_asset_table("frontend_toolings")
    _drop_design_asset_table("frontend_page_structures")
    _drop_context_pack_asset_fields()
    _drop_asset_fields("db_model_drafts")
    _drop_asset_fields("api_contract_drafts")
    _drop_asset_fields("project_blueprints")
    op.drop_table("change_sets")
    _drop_business_story_fields()
    op.drop_column("projects", "prompt_preferences")
    op.drop_column("projects", "coding_preferences")
    op.drop_column("projects", "global_constraints")


def _add_project_config_fields() -> None:
    op.add_column(
        "projects",
        sa.Column("global_constraints", json_type, nullable=False, server_default="[]"),
    )
    op.add_column(
        "projects",
        sa.Column("coding_preferences", json_type, nullable=False, server_default="[]"),
    )
    op.add_column(
        "projects",
        sa.Column("prompt_preferences", json_type, nullable=False, server_default="[]"),
    )


def _add_business_story_fields() -> None:
    op.add_column(
        "business_requirement_stories",
        sa.Column(
            "implementation_scope",
            sa.String(length=50),
            nullable=False,
            server_default="fullstack",
        ),
    )
    op.add_column(
        "business_requirement_stories",
        sa.Column("affected_layers", json_type, nullable=False, server_default="[]"),
    )
    op.add_column(
        "business_requirement_stories",
        sa.Column("depends_on", json_type, nullable=False, server_default="[]"),
    )
    op.add_column(
        "business_requirement_stories",
        sa.Column("source_requirement_ids", json_type, nullable=False, server_default="[]"),
    )
    op.add_column(
        "business_requirement_stories",
        sa.Column("execution_notes", sa.Text(), nullable=True),
    )


def _drop_business_story_fields() -> None:
    op.drop_column("business_requirement_stories", "execution_notes")
    op.drop_column("business_requirement_stories", "source_requirement_ids")
    op.drop_column("business_requirement_stories", "depends_on")
    op.drop_column("business_requirement_stories", "affected_layers")
    op.drop_column("business_requirement_stories", "implementation_scope")


def _create_change_sets() -> None:
    op.create_table(
        "change_sets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("source_requirement_id", sa.Uuid(), nullable=True),
        sa.Column("source_story_id", sa.Uuid(), nullable=True),
        sa.Column("generation_run_id", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column(
            "implementation_scope",
            sa.String(length=50),
            nullable=False,
            server_default="fullstack",
        ),
        sa.Column("affected_layers", json_type, nullable=False, server_default="[]"),
        sa.Column("impact_summary", sa.Text(), nullable=True),
        sa.Column("module_changes", json_type, nullable=False, server_default="{}"),
        sa.Column("risks", json_type, nullable=False, server_default="[]"),
        sa.Column("open_questions", json_type, nullable=False, server_default="[]"),
        sa.Column(
            "recommended_prompt_strategy",
            json_type,
            nullable=False,
            server_default="{}",
        ),
        sa.Column("content", json_type, nullable=False, server_default="{}"),
        sa.Column("diff_from_previous", json_type, nullable=False, server_default="{}"),
        sa.Column("summary", sa.Text(), nullable=True),
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
        "source_requirement_id",
        "source_story_id",
        "generation_run_id",
        "status",
        "created_at",
    ):
        op.create_index(op.f(f"ix_change_sets_{column}"), "change_sets", [column])


def _add_asset_fields(table_name: str) -> None:
    op.add_column(table_name, sa.Column("source_requirement_id", sa.Uuid(), nullable=True))
    op.add_column(table_name, sa.Column("source_story_id", sa.Uuid(), nullable=True))
    op.add_column(table_name, sa.Column("change_set_id", sa.Uuid(), nullable=True))
    op.add_column(table_name, sa.Column("generation_run_id", sa.Uuid(), nullable=True))
    op.add_column(
        table_name,
        sa.Column("diff_from_previous", json_type, nullable=False, server_default="{}"),
    )
    _create_asset_indexes_and_fks(table_name)


def _drop_asset_fields(table_name: str) -> None:
    _drop_asset_indexes_and_fks(table_name)
    op.drop_column(table_name, "diff_from_previous")
    op.drop_column(table_name, "generation_run_id")
    op.drop_column(table_name, "change_set_id")
    op.drop_column(table_name, "source_story_id")
    op.drop_column(table_name, "source_requirement_id")


def _add_context_pack_asset_fields() -> None:
    op.add_column(
        "context_packs",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    _add_asset_fields("context_packs")


def _drop_context_pack_asset_fields() -> None:
    _drop_asset_fields("context_packs")
    op.drop_column("context_packs", "version")


def _create_asset_indexes_and_fks(table_name: str) -> None:
    references = {
        "source_requirement_id": "requirements",
        "source_story_id": "business_requirement_stories",
        "change_set_id": "change_sets",
        "generation_run_id": "generation_runs",
    }
    for column, target_table in references.items():
        op.create_index(op.f(f"ix_{table_name}_{column}"), table_name, [column])
        op.create_foreign_key(
            op.f(f"fk_{table_name}_{column}_{target_table}"),
            table_name,
            target_table,
            [column],
            ["id"],
            ondelete="SET NULL",
        )


def _drop_asset_indexes_and_fks(table_name: str) -> None:
    references = {
        "generation_run_id": "generation_runs",
        "change_set_id": "change_sets",
        "source_story_id": "business_requirement_stories",
        "source_requirement_id": "requirements",
    }
    for column, target_table in references.items():
        op.drop_constraint(
            op.f(f"fk_{table_name}_{column}_{target_table}"),
            table_name,
            type_="foreignkey",
        )
        op.drop_index(op.f(f"ix_{table_name}_{column}"), table_name=table_name)


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
        "source_requirement_id",
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
        "source_requirement_id",
        "project_id",
    ):
        op.drop_index(op.f(f"ix_{table_name}_{column}"), table_name=table_name)
    op.drop_table(table_name)
