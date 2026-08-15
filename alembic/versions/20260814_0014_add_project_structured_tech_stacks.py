"""add structured project tech stacks

Revision ID: 20260814_0014
Revises: 20260808_0013
Create Date: 2026-08-14 00:00:00

"""

from __future__ import annotations

from collections.abc import Sequence
import json

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260814_0014"
down_revision: str | None = "20260808_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_FRONTEND_STACK = "Next.js + React + TypeScript + Tailwind CSS 4 + Shadcn/ui + pnpm"
DEFAULT_BACKEND_STACK = (
    "Python 3.12 + FastAPI + Uvicorn + SQLAlchemy 2.x + Alembic + PostgreSQL + uv"
)

TECH_TYPES = {
    "framework",
    "language",
    "ui_library",
    "package_manager",
    "database",
    "orm",
    "migration_tool",
    "runtime",
    "build_tool",
}


def _split_stack_text(value: str | None) -> list[str]:
    if not value:
        return []
    parts = []
    for chunk in value.replace("\n", " + ").replace(",", " + ").replace("；", " + ").replace("、", " + ").split("+"):
        item = chunk.strip()
        if item:
            parts.append(item)
    return parts


def _infer_type(name: str) -> str:
    lowered = name.lower()
    rules = [
        ("orm", ["prisma", "sqlalchemy", "sqlmodel", "typeorm", "drizzle", "sequelize", "peewee"]),
        ("migration_tool", ["alembic", "flyway", "liquibase", "drizzle kit"]),
        ("package_manager", ["pnpm", "npm", "yarn", "bun"]),
        ("runtime", ["node.js", "nodejs", "python", "deno", "bun", "uvicorn"]),
        ("build_tool", ["vite", "webpack", "turbopack", "esbuild", "rollup"]),
        ("database", ["postgres", "mysql", "sqlite", "mongodb", "redis"]),
        ("language", ["typescript", "javascript", "python", "go", "java", "kotlin", "ruby", "php", "rust"]),
        ("ui_library", ["react", "vue", "svelte", "shadcn/ui", "tailwind", "mui", "chakra", "antd", "radix", "lucide"]),
        ("framework", ["next.js", "nextjs", "nuxt", "remix", "sveltekit", "angular", "astro", "litestar", "django", "fastapi", "flask", "gin", "echo", "rails", "laravel"]),
    ]
    for stack_type, patterns in rules:
        if any(pattern in lowered for pattern in patterns):
            return stack_type
    return "framework"


def _normalize_items(value: str | list[dict[str, object]] | None, default: str) -> list[dict[str, object]]:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("[") or stripped.startswith("{"):
            try:
                decoded = json.loads(stripped)
            except json.JSONDecodeError:
                decoded = None
            if isinstance(decoded, list) and decoded:
                value = decoded  # type: ignore[assignment]
    if isinstance(value, list) and value:
        items = []
        for item in value:
            if isinstance(item, dict) and isinstance(item.get("name"), str):
                tech_type = item.get("type")
                if isinstance(tech_type, str) and tech_type in TECH_TYPES:
                    item_type = tech_type
                else:
                    item_type = _infer_type(item["name"])
                items.append(
                    {
                        "name": item["name"].strip(),
                        "type": item_type,
                        "tags": item.get("tags") if isinstance(item.get("tags"), list) else [],
                        "role": item.get("role") if isinstance(item.get("role"), str) else None,
                    }
                )
        if items:
            return items
    names = _split_stack_text(value if isinstance(value, str) else default)
    return [{"name": name, "type": _infer_type(name), "tags": [], "role": None} for name in names]


def upgrade() -> None:
    bind = op.get_bind()
    json_type = sa.JSON().with_variant(postgresql.JSONB, "postgresql")
    op.add_column(
        "projects",
        sa.Column(
            "target_frontend_stack_items",
            json_type,
            nullable=False,
            server_default="[]",
        ),
    )
    op.add_column(
        "projects",
        sa.Column(
            "target_backend_stack_items",
            json_type,
            nullable=False,
            server_default="[]",
        ),
    )

    rows = bind.execute(
        sa.text(
            """
            SELECT id, target_frontend_stack, target_backend_stack,
                   target_frontend_stack_items, target_backend_stack_items
            FROM projects
            """
        )
    ).mappings()
    for row in rows:
        frontend_items = _normalize_items(
            row.get("target_frontend_stack_items"),
            row.get("target_frontend_stack") or DEFAULT_FRONTEND_STACK,
        )
        backend_items = _normalize_items(
            row.get("target_backend_stack_items"),
            row.get("target_backend_stack") or DEFAULT_BACKEND_STACK,
        )
        bind.execute(
            sa.text(
                """
                UPDATE projects
                SET target_frontend_stack_items = :frontend_items,
                    target_backend_stack_items = :backend_items
                WHERE id = :project_id
                """
            ),
            {
                "project_id": row["id"],
                "frontend_items": json.dumps(frontend_items, ensure_ascii=False),
                "backend_items": json.dumps(backend_items, ensure_ascii=False),
            },
        )


def downgrade() -> None:
    op.drop_column("projects", "target_backend_stack_items")
    op.drop_column("projects", "target_frontend_stack_items")
