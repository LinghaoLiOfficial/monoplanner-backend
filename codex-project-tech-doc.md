# Project Technical Documentation

## Overview

本项目是 `Fullstack Context Orchestrator API` 后端，目标是把自然语言业务需求编排为业务需求故事池、结构化 Project Blueprint，并继续生成 API 契约草案、数据库模型草案、Codex Context Pack 和基础一致性检查结果。当前实现包含数据库、API、schema、service layer、OpenAI-compatible 真实 LLM 生成链路；业务需求故事生成要求真实 LLM 配置，未配置时返回 503；部分后续生成器未配置 LLM 时仍保留 deterministic fallback；当前 Project Blueprint 生成器按阶段要求固定使用 deterministic mock，不接入真实 LLM。

## Architecture

- Web 框架：FastAPI，统一 API 前缀为 `/api/v1`。
- 数据库：SQLAlchemy 2.x 同步 `Session`，运行时使用 `postgresql+psycopg://...`。
- Migration：Alembic 读取 `app.db.base.Base.metadata`。
- 分层约定：endpoint 负责请求/响应和依赖注入，业务逻辑放在 `app/services/`，LLM 生成入口放在 `app/generators/`，统一 LLM JSON 调用封装放在 `app/llm/`。
- 配置：项目不区分开发、测试、生产环境，只读取根目录单个 `.env`。
- LLM：业务需求故事池使用 `app/llm/client.py` 中基于 `httpx` 的 OpenAI-compatible `/chat/completions` client，缺少 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL` 时返回 503，不生成 mock 数据；其他结构化生成器使用 `.venv` 中的 `monobase.llm` 调用 OpenAI-compatible `chat/completions`，缺少必填参数时使用 deterministic fallback。
- Blueprint 生成：`app/generators/blueprint_generator.py` 中 `build_mock_blueprint_content` 始终委托 `build_deterministic_blueprint_content`，读取 `Project.target_frontend_stack` 和 `Project.target_backend_stack`，输出 JSON 中保留简短键 `tech_stack.frontend/backend`。
- 业务需求池：位于 Requirement 和 Blueprint 之间，`POST /projects/{project_id}/generate/business-stories` 会把最新或指定 Requirement 拆解为垂直切片故事，保存到 `business_requirement_stories` 并记录 `GenerationRun`；Blueprint 生成时若已有业务故事，会把精简故事列表写入 `content.business_requirement_stories`。
- 响应约定：核心接口按任务定义直接返回资源本体或列表，不使用旧 `ApiResponse` 包装。
- 项目列表：`GET /api/v1/projects` 支持可选 `q` 参数，service layer 对 `q` 做 trim，非空时按 `Project.name.ilike("%q%")` 大小写不敏感模糊搜索，结果仍按 `created_at desc` 排序。
- 项目名称：`Project.name` 在 service layer 创建和更新时会 trim，trim 后为空返回 400；完全相同名称返回 409；数据库通过普通 unique 约束兜底，当前唯一性大小写敏感但忽略首尾空格。
- 项目描述：`ProjectCreate.description` 为可选字段；创建项目时前端可以只传 `name`，响应 `ProjectRead` 仍保留 `description` 字段，未传时为 `null`。
- 删除策略：`DELETE /api/v1/projects/{project_id}` 在 `ProjectService.delete_project` 中执行，删除失败会 rollback；Requirement、Blueprint、GenerationRun、BusinessRequirementStory 和结构化草案表通过既有 `ondelete="CASCADE"` 外键和 relationship cascade 清理。
- JSON 约定：模型层使用 `JSON().with_variant(JSONB, "postgresql")`，兼容 PostgreSQL JSONB 和 SQLite 测试。
- CORS：只读取 `BACKEND_CORS_ORIGINS`，逗号分隔。

## Key Files and Directories

- `app/models/`: `Project`、`Requirement`、`BusinessRequirementStory`、`ProjectBlueprint`、`GenerationRun`、`ApiContractDraft`、`DbModelDraft`、`ContextPack` ORM 模型。
- `app/schemas/`: 各资源的 request/response Pydantic schema，response schema 使用 `from_attributes=True`。
- `app/api/v1/endpoints/`: health、projects、requirements、business_requirement_stories、blueprints、generation、api_contracts、db_models、context_packs、consistency routes。
- `app/services/`: Project/Requirement/BusinessRequirementStory/BusinessStoryGeneration/Blueprint/Generation 以及 API contract、DB model、Context Pack、一致性检查服务；项目列表搜索和删除事务边界位于 `ProjectService`。
- `app/generators/`: blueprint、API contract、DB model、Context Pack 生成入口；当前 blueprint 固定 deterministic mock，其余生成器有 LLM 必填配置时调用真实 LLM、无配置时使用 deterministic fallback；consistency checker 仍为本地规则检查。
- `app/llm/json_client.py`: 统一构造 `monobase.llm.LLMConfig`，调用真实文本模型，并解析/校验 JSON object 输出。
- `app/llm/client.py`: 业务需求故事池专用 OpenAI-compatible `httpx` client，负责配置校验、timeout、非 2xx 处理和 response content 提取。
- `app/prompts/business_story_decomposer.py`: 业务需求故事分解 system prompt 和 user payload builder，约束严格 JSON、垂直切片、优先级定义和禁止事项。
- `alembic/versions/20260708_0002_create_orchestrator_tables.py`: 创建第一批核心业务表。
- `alembic/versions/20260708_0003_create_structured_draft_tables.py`: 创建第二批结构化草案表。
- `alembic/versions/20260709_0004_add_unique_constraint_to_project_name.py`: 为 `projects.name` 添加普通唯一约束。
- `alembic/versions/20260710_0005_create_business_requirement_stories.py`: 创建业务需求故事池表和索引。
- `tests/`: 使用 SQLite 内存库验证 API、生成链路和 cascade 行为。

## Setup and Runbook

项目只使用根目录单个 `.env`，保留 `.env.example` 作为唯一配置模板：

```bash
cp .env.example .env
```

`.env.example` 模板：

```env
APP_NAME=Fullstack Context Orchestrator API
BACKEND_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
DATABASE_URL=postgresql+psycopg://llh@localhost:5432/context_orchestrator
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=replace-with-your-api-key
LLM_MODEL=qwen-plus
LLM_TIMEOUT=60
LLM_TIMEOUT_SECONDS=60
LLM_THINKING=false
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

本机 PostgreSQL：

```bash
brew services start postgresql@14
uv run python -m alembic upgrade head
```

Docker 开发数据库仍可用：

```bash
docker compose up -d db
```

## Testing and Verification

当前验证结果：

- `uv run python -m ruff check .` 通过。
- `uv run python -m pytest` 通过，38 个测试全部通过。
- `uv run python -m alembic upgrade head` 最近一次手动迁移验证到 `20260708_0003`；当前新增 `20260709_0004` 会为 `projects.name` 添加普通唯一约束，历史重复数据需先清理；`20260710_0005` 会创建 `business_requirement_stories`。
- 当前环境中 `uv run <console-script>` 可能出现 spawn 失败，因此 Makefile 使用 `uv run python -m ...` 调用 alembic、uvicorn、ruff 和 pytest。

测试覆盖：

- health 响应。
- Project CRUD、404。
- Project 创建不要求 `description`；创建和更新项目名会 trim；空白或 null 项目名返回 400；重复项目名返回 409。
- Project 列表支持 `q` 按名称大小写不敏感模糊搜索，空白 `q` 等同于不搜索。
- Requirement 创建和按项目倒序列表。
- 无需求生成 blueprint 返回 400，并记录 failed `GenerationRun`。
- 有需求生成 blueprint、列表和详情查询；blueprint content 包含 `tech_stack.frontend/backend`；当前按阶段要求始终走 deterministic mock。
- 业务需求故事生成覆盖 Project/Requirement 缺失、LLM 未配置 503、合法 LLM JSON 保存、非法输出 502、overwrite 重建、列表过滤、详情、PATCH 更新、`GenerationRun` completed/failed 记录。
- Blueprint 生成在项目已有业务需求故事时，会在 `content.business_requirement_stories` 中包含故事标题、优先级、状态和用户故事；无故事时保持原逻辑。
- Blueprint 生成器内部未知异常会记录 failed `GenerationRun`，并转换为中文可读 HTTP 500。
- 生成 API contract、DB model、Context Pack，支持列表、详情、role 过滤和 Markdown 导出；无 LLM 必填配置时走 deterministic fallback。
- Context Pack 可在缺少 API contract 或 DB model 时生成，并在 prompt 中标记缺失上下文。
- Consistency check 覆盖 warning 和 passed 状态。
- 删除 Project 后关联 Requirement、BusinessRequirementStory、GenerationRun 和第二批结构化草案 cascade 清理。
- 删除 Project 后项目详情和按项目访问 requirements、blueprints、api-contracts、db-models、context-packs 均返回 404，已删除关联资源详情不可再访问。
- 旧 auth/template_items 占位接口保持测试通过。

## Current Decisions and Conventions

- 新任务定义优先于旧 scaffold 定义；不保留旧环境变量兼容层。
- 新核心接口不使用旧 `ApiResponse` 包装。
- `ProjectBlueprint.content`、`GenerationRun` snapshots 和第二批 draft/context content 在 PostgreSQL 使用 JSONB，在测试 SQLite 中使用 SQLAlchemy JSON variant。
- `Project.name` 当前采用普通唯一约束，因此大小写敏感；service layer 会先 trim 再查重，并捕获数据库 `IntegrityError` 转成业务 409。
- `GenerationRun` 记录 `generate_api_contract`、`generate_db_model`、`generate_context_packs` 的 completed/failed 状态。
- `GenerationRun` 记录 `generate_business_requirement_stories` 的 completed/failed 状态；成功输出快照包含故事数量、优先级统计和 story ids，失败输出快照为空并保存错误信息。
- 业务需求故事优先级固定为 `p1_must`、`p2_should`、`p3_could`、`p4_wont`；状态固定为 `draft`、`ready`、`in_progress`、`done`、`deferred`，生成默认 `draft`。
- 业务需求故事 LLM 输出必须是 JSON object，顶层含 `stories` list；每个故事必须含 `title`、`priority`、`user_story`、`business_scope`、`data_rules`、`acceptance_criteria`，其中 `business_scope` 必须含 `included` 和 `excluded`。
- Blueprint、API contract 和 DB model 每次生成创建新记录，version 从 1 开始递增。
- `Project` ORM 技术栈字段为 `target_frontend_stack` 和 `target_backend_stack`；读取 ORM 对象时不要使用旧字段名 `frontend_stack` 或 `backend_stack`。
- Context Pack 第一批固定生成 `frontend_engineer` 和 `backend_engineer` 两种角色。
- Markdown export 返回 JSON：`filename`、`content_type`、`content`，不返回文件流。
- LLM 输出必须是 JSON object；`app/llm/json_client.py` 会兼容去除外层 Markdown code fence 后解析 JSON。
- LLM 请求不传入 `max_tokens` 或 `temperature`，项目侧不设置输出 token 上限和生成温度，相关行为交由模型服务默认策略处理。
- 当前 README、`.env.example` 和 `.env` 使用 DashScope OpenAI-compatible 示例：`https://dashscope.aliyuncs.com/compatible-mode/v1` + `qwen-plus`。

## Known Issues and Follow-ups

- 尚未实现登录注册、复杂权限、多用户协作、审计、限流和生产监控。
- Consistency check 当前只做基础结构一致性检查，后续可扩展为 schema/endpoint/DB 字段级别校验。
- Context Pack prompt 在真实运行时由 LLM 生成；测试 fallback 仍使用本地模板文案，后续可扩展为可配置模板和版本管理。
- TestClient 当前有 StarletteDeprecationWarning，提示未来可能需要使用 `httpx2`。
- 如果已有数据库中存在完全相同的 `projects.name`，迁移 `20260709_0004` 会失败；上线前需要先清理历史重复数据。若未来要求大小写不敏感唯一，可改为 PostgreSQL functional unique index，如 `lower(name)`。
