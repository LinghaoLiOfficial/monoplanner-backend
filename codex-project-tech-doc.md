# Project Technical Documentation

## Overview

本项目是 `Fullstack Context Orchestrator API` 后端，目标是把自然语言业务需求编排为业务需求故事池、结构化 Project Blueprint，并继续生成 API 契约草案、数据库模型草案、Codex Context Pack 和基础一致性检查结果。当前实现包含数据库、API、schema、service layer、OpenAI-compatible 真实 LLM 生成链路；业务需求故事、Project Blueprint、API Contract Draft 和 Db Model Draft 生成均默认要求真实 LLM 配置，未配置时返回 503，不静默生成 mock 数据；LLM 请求失败或结构化输出错误返回 502 并记录 failed `GenerationRun`。

## Architecture

- Web 框架：FastAPI，统一 API 前缀为 `/api/v1`。
- 数据库：SQLAlchemy 2.x 同步 `Session`，运行时使用 `postgresql+psycopg://...`。
- Migration：Alembic 读取 `app.db.base.Base.metadata`。
- 分层约定：endpoint 负责请求/响应和依赖注入，业务逻辑放在 `app/services/`，LLM 生成入口放在 `app/generators/`，统一 LLM JSON 调用封装放在 `app/llm/`。
- 配置：项目不区分开发、测试、生产环境，只读取根目录单个 `.env`。
- LLM：业务需求故事池和结构化生成器统一使用 `app/llm/client.py` 的 OpenAI-compatible Chat Completions；缺少 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL` 时返回 503，不生成 mock 数据。`OpenAICompatibleLLMClient.stream()` 支持 OpenAI-compatible streaming chat completions，解析 `data: ...` SSE chunk 并产出 `choices[0].delta.content`、`choices[0].message.content` 或 `choices[0].text`；空 `choices`、usage-only chunk 和非法 JSON chunk 视为可忽略供应商 metadata，provider error chunk 仍抛错。
- 后端内部流式聚合：`POST /api/v1/projects/{project_id}/generate/business-stories`、`/blueprint`、`/api-contract`、`/db-model` 是当前主流程，HTTP 返回普通 JSON；内部通过 `app/services/llm_generation_runtime.py` 使用 LLM `stream=true` 读取完整文本，随后清洗 fenced JSON、解析、结构校验、保存数据库并返回保存后的资源。
- 长耗时任务执行方式：当前未接入 Celery、RQ、Redis 队列、独立 worker 或 FastAPI `BackgroundTasks`。LLM 生成在请求处理过程中同步执行并等待模型返回；`GenerationRun` 用于记录进度、状态、错误和输出快照，不是消息队列任务表。
- 轻量后台队列候选方案：若要把 LLM 生成改为后台执行，优先考虑扩展 `GenerationRun` 为 PostgreSQL-backed queue，新增 `queued` 状态、锁字段、重试字段和 worker 进程；endpoint 只校验前置条件并创建 queued run，worker 使用 `SELECT ... FOR UPDATE SKIP LOCKED` 领取任务后复用生成链路。内存队列或 FastAPI `BackgroundTasks` 只适合本地 demo，不适合作为可靠任务队列。
- SSE 兼容接口：`POST /api/v1/projects/{project_id}/generate/{module}/stream` 仍保留 `text/event-stream` 路由，但不再逐 token 返回 `delta`，只包装同一套内部流式聚合流程并发送 `start`、`saved`、`done` 或 `error` 事件。新前端主流程应调用普通 JSON 接口，再通过读取接口获取保存后的数据库资源。
- Blueprint 生成：`app/generators/blueprint_generator.py` 默认调用 LLM，读取 `Project.target_frontend_stack` 和 `Project.target_backend_stack`，输入最新 Requirement 和业务需求故事列表，输出经后端校验和规范化后保存到 `ProjectBlueprint.content`；deterministic helper 仅作为开发辅助保留。
- 业务需求池：位于 Requirement 和 Blueprint 之间，`POST /projects/{project_id}/generate/business-stories` 会把最新或指定 Requirement 拆解为垂直切片故事，保存到 `business_requirement_stories` 并记录绑定 `requirement_id` 的 `GenerationRun`；`GET /projects/{project_id}/requirements` 会在每条需求响应中附带最新 `business_story_generation`，`GET /requirements/{requirement_id}/business-story-generation` 可轮询单条需求最新生成状态；`PATCH /business-stories/{story_id}` 支持局部更新标题、优先级、状态、用户故事、业务范围、数据规则和验收标准，其中可编辑 JSON 字段在 service 层规范化后整体赋值保存；`DELETE /business-stories/{story_id}` 硬删除单条故事并返回 204；Blueprint 生成时若已有业务故事，会把精简故事列表写入 `content.business_requirement_stories`。
- 用户需求历史进度文案：`business_story_generation.message` 是原始用户需求历史中业务需求故事进度条可消费的用户可见提示，业务故事模块使用“更新”语义，如“正在更新业务需求故事...”“业务需求故事已更新。”“业务需求故事更新失败”；保留 `/generate/...` 路径、`run_type="generate_business_requirement_stories"` 和 `GenerationRun` 等技术标识不变。
- 响应约定：核心接口按任务定义直接返回资源本体或列表，不使用旧 `ApiResponse` 包装。
- 项目列表：`GET /api/v1/projects` 支持可选 `q` 参数，service layer 对 `q` 做 trim，非空时按 `Project.name.ilike("%q%")` 大小写不敏感模糊搜索，结果仍按 `created_at desc` 排序。
- 项目名称：`Project.name` 在 service layer 创建和更新时会 trim，trim 后为空返回 400；完全相同名称返回 409；数据库通过普通 unique 约束兜底，当前唯一性大小写敏感但忽略首尾空格。
- 项目描述：`ProjectCreate.description` 为可选字段；创建项目时前端可以只传 `name`，响应 `ProjectRead` 仍保留 `description` 字段，未传时为 `null`。
- 删除策略：`DELETE /api/v1/projects/{project_id}` 在 `ProjectService.delete_project` 中执行，删除失败会 rollback；Requirement、Blueprint、GenerationRun、BusinessRequirementStory 和结构化草案表通过既有 `ondelete="CASCADE"` 外键和 relationship cascade 清理。`DELETE /api/v1/business-stories/{story_id}` 在 `BusinessRequirementStoryService.delete_story` 中硬删除单条故事，删除失败会 rollback，不影响项目、需求、蓝图或其他故事。
- JSON 约定：模型层使用 `JSON().with_variant(JSONB, "postgresql")`，兼容 PostgreSQL JSONB 和 SQLite 测试。
- CORS：只读取 `BACKEND_CORS_ORIGINS`，逗号分隔。

## Key Files and Directories

- `app/models/`: `Project`、`Requirement`、`BusinessRequirementStory`、`ProjectBlueprint`、`GenerationRun`、`ApiContractDraft`、`DbModelDraft`、`ContextPack` ORM 模型。
- `app/schemas/`: 各资源的 request/response Pydantic schema，response schema 使用 `from_attributes=True`。
- `app/api/v1/endpoints/`: health、projects、requirements、business_requirement_stories、blueprints、generation、api_contracts、db_models、context_packs、consistency routes。
- `app/services/`: Project/Requirement/BusinessRequirementStory/BusinessStoryGeneration/Blueprint/Generation 以及 API contract、DB model、Context Pack、一致性检查服务；项目列表搜索和删除事务边界位于 `ProjectService`。
- `app/services/llm_generation_runtime.py`: 后端内部 LLM stream 聚合工具，负责调用 `OpenAICompatibleLLMClient.stream()` 并拼接完整 raw text。
- `app/services/streaming_generation_service.py`: 四类 LLM 生成的共享编排层，负责创建和更新 `GenerationRun`、调用内部流式聚合、JSON 解析、结构校验、资源保存、错误映射和 SSE 兼容事件序列化。
- `app/generators/`: blueprint、API contract、DB model、Context Pack 生成入口；blueprint、API contract、DB model 默认调用真实 LLM 并做结构校验和规范化；consistency checker 仍为本地规则检查。
- `app/llm/json_client.py`: JSON 清洗和解析工具，兼容纯 JSON、Markdown fenced JSON 和前后少量解释文本；旧非流式调用入口仍存在，但四个主生成接口不再依赖它发起 LLM 请求。
- `app/prompts/business_story_decomposer.py`: 业务需求故事分解 system prompt 和 user payload builder，约束严格 JSON、垂直切片、优先级定义和禁止事项。
- `app/prompts/blueprint_generator.py`、`app/prompts/api_contract_generator.py`、`app/prompts/db_model_generator.py`: 三类结构化草案的 system prompt 和 user payload builder。
- `alembic/versions/20260708_0002_create_orchestrator_tables.py`: 创建第一批核心业务表。
- `alembic/versions/20260708_0003_create_structured_draft_tables.py`: 创建第二批结构化草案表。
- `alembic/versions/20260709_0004_add_unique_constraint_to_project_name.py`: 为 `projects.name` 添加普通唯一约束。
- `alembic/versions/20260710_0005_create_business_requirement_stories.py`: 创建业务需求故事池表和索引。
- `alembic/versions/20260711_0006_add_generation_run_progress.py`: 为 `generation_runs` 增加 `requirement_id`、`progress`、`message`，支持前端刷新后恢复业务故事生成进度。
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
- `uv run python -m pytest` 通过，69 个测试全部通过。
- `uv run python -m alembic upgrade head` 最近一次手动迁移验证到 `20260708_0003`；当前新增 `20260709_0004` 会为 `projects.name` 添加普通唯一约束，历史重复数据需先清理；`20260710_0005` 会创建 `business_requirement_stories`；`20260711_0006` 会扩展 `generation_runs` 以支持需求绑定和进度持久化。
- 当前环境中 `uv run <console-script>` 可能出现 spawn 失败，因此 Makefile 使用 `uv run python -m ...` 调用 alembic、uvicorn、ruff 和 pytest。
- 当前仓库 `.venv/bin/pytest` console script 的 shebang 仍指向旧目录，测试时可直接使用 `.venv/bin/python -m pytest`。

测试覆盖：

- health 响应。
- Project CRUD、404。
- Project 创建不要求 `description`；创建和更新项目名会 trim；空白或 null 项目名返回 400；重复项目名返回 409。
- Project 列表支持 `q` 按名称大小写不敏感模糊搜索，空白 `q` 等同于不搜索。
- Requirement 创建和按项目倒序列表；Requirement 响应包含 `business_story_generation`，无生成任务时为 `null`。
- 无需求生成 blueprint 返回 400，并记录 failed `GenerationRun`。
- 有需求生成 blueprint、列表和详情查询；blueprint content 包含 `tech_stack.frontend/backend`；当前按阶段要求始终走 deterministic mock。
- 业务需求故事生成覆盖 Project/Requirement 缺失、无效 `requirement_id` 400、LLM 未配置 503、合法 LLM JSON 保存、非法输出 502、0 条故事失败、`overwrite=false` 追加、`overwrite=true` 重建、列表过滤、详情、PATCH 局部更新、可编辑 JSON 字段规范化、非法格式、单条 DELETE 删除、删除不存在 404、`GenerationRun` succeeded/failed 进度记录和最新状态查询。
- 内部流式聚合测试覆盖普通 JSON 生成接口、SSE 兼容 headers、`start -> saved -> done` 兼容事件顺序、四类资源保存、fenced JSON 清洗、LLM 未配置/请求失败/非法 JSON/0 条故事/保存失败的普通 JSON 错误或 failed `GenerationRun`。
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
- `GenerationRun` 记录 `generate_blueprint`、`generate_api_contract`、`generate_db_model`、`generate_context_packs` 的 running/completed/failed 状态。
- `GenerationRun` 成功状态统一写 `completed`；业务故事状态查询接口会把 `completed` 兼容映射为前端既有 `succeeded`。成功 `output_snapshot` 记录 `raw_text_length`、资源 id 或资源 id 列表、counts 和 summary；失败 `output_snapshot` 记录 `failure_stage` 和可选 `raw_text_length`，并保存 `error_message`。
- 业务需求故事优先级固定为 `p1_must`、`p2_should`、`p3_could`、`p4_wont`；状态固定为 `draft`、`ready`、`in_progress`、`done`、`deferred`，生成默认 `draft`。
- 业务需求故事 LLM 输出必须是 JSON object，顶层含非空 `stories` list；每个故事必须含 `title`、`priority`、`user_story`、`business_scope`、`data_rules`、`acceptance_criteria`，其中 `business_scope` 会规范化为 `included` 和 `excluded`。若未生成任何有效故事，生成任务失败并记录“未生成有效业务需求故事。”。
- 业务需求故事 PATCH 使用 `model_dump(exclude_unset=True)` 做局部更新；`user_story` 保存 trim 后非空字符串；`business_scope` 保存为 `{"included": list[str], "excluded": list[str]}`，缺失项补空数组；`data_rules` 允许 `{rule}` 或 `{field, rule}`，过滤空 rule；`acceptance_criteria` trim 并过滤空字符串。
- 业务需求故事生成会向 LLM 请求传入 `response_format={"type":"json_object"}`；主生成流程不再发起二次非流式 JSON 修复，解析或结构校验失败直接返回 502 并记录 failed `GenerationRun`。
- Blueprint、API contract 和 DB model 每次生成创建新记录，version 从 1 开始递增。
- `Project` ORM 技术栈字段为 `target_frontend_stack` 和 `target_backend_stack`；读取 ORM 对象时不要使用旧字段名 `frontend_stack` 或 `backend_stack`。
- Context Pack 第一批固定生成 `frontend_engineer` 和 `backend_engineer` 两种角色。
- Markdown export 返回 JSON：`filename`、`content_type`、`content`，不返回文件流。
- LLM 输出必须是 JSON object；`app/llm/json_client.py` 会兼容去除外层 Markdown code fence 后解析 JSON。
- `POST /api/v1/projects/{project_id}/generate/blueprint`、`/api-contract`、`/db-model` 默认不再静默 fallback 到 deterministic 数据；`LLM_API_KEY`、`LLM_BASE_URL` 或 `LLM_MODEL` 缺失返回 503，LLM 请求失败或结构化输出错误返回 502，并完整记录 `GenerationRun` failed。
- 普通生成接口的业务前置错误（如项目、需求、蓝图缺失）仍使用普通 HTTP 4xx 且不创建 `GenerationRun`；LLM 配置、请求、空输出、格式、校验和保存失败均返回普通 JSON 错误，并记录 failed `GenerationRun`。SSE 兼容接口在流建立后通过 `data: {"type":"error",...}` 表达同类失败。
- LLM 请求不传入 `max_tokens` 或 `temperature`，项目侧不设置输出 token 上限和生成温度，相关行为交由模型服务默认策略处理。
- 当前 README、`.env.example` 和 `.env` 使用 DashScope OpenAI-compatible 示例：`https://dashscope.aliyuncs.com/compatible-mode/v1` + `qwen-plus`。

## Known Issues and Follow-ups

- 尚未实现登录注册、复杂权限、多用户协作、审计、限流和生产监控。
- Consistency check 当前只做基础结构一致性检查，后续可扩展为 schema/endpoint/DB 字段级别校验。
- Context Pack prompt 在真实运行时由 LLM 生成；测试 fallback 仍使用本地模板文案，后续可扩展为可配置模板和版本管理。
- Blueprint、API Contract、DB Model 已默认接入 LLM，测试通过 monkeypatch/mock `generate_json` 返回结构化 payload；真实模型环境仍需人工端到端验收。
- TestClient 当前有 StarletteDeprecationWarning，提示未来可能需要使用 `httpx2`。
- 如果已有数据库中存在完全相同的 `projects.name`，迁移 `20260709_0004` 会失败；上线前需要先清理历史重复数据。若未来要求大小写不敏感唯一，可改为 PostgreSQL functional unique index，如 `lower(name)`。
