# Project Technical Documentation

## Overview

本项目是 `Fullstack Context Orchestrator API` 后端，目标是为“全栈开发上下文编排器”提供第一批基础 API。当前实现只包含数据库、API、schema、service layer 和 deterministic mock blueprint generator，不接入 OpenAI、Claude、LangChain、LlamaIndex 或任何真实 AI 服务。

## Architecture

- Web 框架：FastAPI，统一 API 前缀为 `/api/v1`。
- 数据库：SQLAlchemy 2.x 同步 `Session`，运行时使用 `postgresql+psycopg://...`。
- Migration：Alembic 读取 `app.db.base.Base.metadata`。
- 分层约定：endpoint 负责请求/响应和依赖注入，业务逻辑放在 `app/services/`，mock 生成逻辑放在 `app/generators/`。
- 响应约定：新核心接口按任务定义直接返回资源本体或列表，不使用旧 `ApiResponse` 包装。
- CORS：只读取 `BACKEND_CORS_ORIGINS`，逗号分隔。

## Key Files and Directories

- `app/models/`: `Project`、`Requirement`、`ProjectBlueprint`、`GenerationRun` ORM 模型。
- `app/schemas/`: 各资源的 request/response Pydantic schema，response schema 使用 `from_attributes=True`。
- `app/api/v1/endpoints/`: health、projects、requirements、blueprints、generation routes。
- `app/services/`: `ProjectService`、`RequirementService`、`BlueprintService`、`GenerationService`。
- `app/generators/blueprint_generator.py`: deterministic mock blueprint 生成器。
- `alembic/versions/20260708_0002_create_orchestrator_tables.py`: 创建四张核心业务表。
- `tests/`: 使用 SQLite 内存库验证 API 和 cascade 行为。

## Setup and Runbook

配置 `.env`：

```env
APP_NAME=Fullstack Context Orchestrator API
APP_ENV=development
BACKEND_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
DATABASE_URL=postgresql+psycopg://orchestrator:orchestrator@localhost:5432/context_orchestrator
```

常用命令：

```bash
uv sync
uv sync --group dev
uv run python -m alembic upgrade head
uv run python -m uvicorn app.main:app --reload
uv run python -m ruff check .
uv run python -m pytest
```

Docker 开发数据库：

```bash
docker compose up -d db
```

## Testing and Verification

当前验证结果：

- `uv run python -m ruff check .` 通过。
- `uv run python -m pytest` 通过，11 个测试全部通过。
- 当前环境中 `uv run <console-script>` 可能出现 spawn 失败，因此 Makefile 使用 `uv run python -m ...` 调用 alembic、uvicorn、ruff 和 pytest。

测试覆盖：

- health 响应。
- Project CRUD、404。
- Requirement 创建和按项目倒序列表。
- 无需求生成 blueprint 返回 400。
- 有需求生成 mock blueprint、列表和详情查询。
- 删除 Project 后关联 Requirement 和 GenerationRun cascade 清理。
- 旧 auth/template_items 占位接口保持测试通过。

## Current Decisions and Conventions

- 新任务定义优先于旧 scaffold 定义；不保留旧环境变量兼容层。
- 新核心接口不使用旧 `ApiResponse` 包装。
- `ProjectBlueprint.content` 和 `GenerationRun` snapshots 在 PostgreSQL 使用 JSONB，在测试 SQLite 中使用 SQLAlchemy JSON variant。
- `GenerationRun` 增加 `updated_at`，以满足 response schema 包含 `id`、`created_at`、`updated_at` 的约定。
- Blueprint 每次生成创建新记录，version 从 1 开始递增。

## Known Issues and Follow-ups

- 尚未接入真实 LLM provider。
- 尚未实现登录注册、复杂权限、多用户协作、审计、限流和生产监控。
- TestClient 当前有 StarletteDeprecationWarning，提示未来可能需要使用 `httpx2`。
