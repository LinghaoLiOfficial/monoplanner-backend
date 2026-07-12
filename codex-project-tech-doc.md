# Project Technical Documentation

## Overview

本项目是 `Fullstack Context Orchestrator API` 后端，目标是把自然语言业务需求编排为业务需求故事池、结构化 Project Blueprint，并继续生成 API 契约草案、数据库模型草案、Codex Context Pack 和基础一致性检查结果。当前实现包含数据库、API、schema、service layer、Cookie/JWT 用户认证、多租户项目权限隔离、管理员用户管理和 OpenAI-compatible 真实 LLM 生成链路；业务需求故事、Project Blueprint、API Contract Draft 和 Db Model Draft 生成均默认要求真实 LLM 配置，未配置时返回 503，不静默生成 mock 数据；LLM 请求失败或结构化输出错误返回 502 并记录 failed `GenerationRun`。

## Architecture

- Web 框架：FastAPI，统一 API 前缀为 `/api/v1`。
- 数据库：SQLAlchemy 2.x 同步 `Session`，所有运行入口统一使用宿主机本地 PostgreSQL；应用/Alembic 默认连接 `postgresql+psycopg://llh@localhost:5432/context_orchestrator`，测试默认连接 `postgresql+psycopg://llh@localhost:5432/context_orchestrator_test`。
- Migration：Alembic 读取 `app.db.base.Base.metadata`。
- 分层约定：endpoint 负责请求/响应和依赖注入，业务逻辑放在 `app/services/`，LLM 生成入口放在 `app/generators/`，统一 LLM JSON 调用封装放在 `app/llm/`。
- 配置：项目不区分开发、测试、生产环境，应用和 Alembic 读取根目录单个 `.env`；pytest 会把 `DATABASE_URL` 覆盖为 `TEST_DATABASE_URL`，并要求测试库名以 `_test` 结尾。
- LLM：业务需求故事池和结构化生成器统一使用 `app/llm/client.py` 的 OpenAI-compatible Chat Completions；缺少 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL` 时返回 503，不生成 mock 数据。`OpenAICompatibleLLMClient.stream()` 支持 OpenAI-compatible streaming chat completions，解析 `data: ...` SSE chunk 并产出 `choices[0].delta.content`、`choices[0].message.content` 或 `choices[0].text`；空 `choices`、usage-only chunk 和非法 JSON chunk 视为可忽略供应商 metadata，provider error chunk 仍抛错。
- 后台生成队列：`POST /api/v1/projects/{project_id}/generate/business-stories`、`/blueprint`、`/api-contract`、`/db-model`、`/context-packs` 当前只做业务前置校验并创建 `GenerationRun(status="queued")`，HTTP 返回 `202 Accepted` 和 `GenerationRunRead`；独立 worker 通过 `uv run python -m app.workers.generation_worker` 启动，使用 PostgreSQL `FOR UPDATE SKIP LOCKED` 领取任务并在后台执行 LLM/Context Pack 生成。单个 worker 入口当前是串行 `run_once()` 循环，`QUEUE_WORKER_CONCURRENCY` 只是配置字段，尚未被 `run_worker_loop()` 消费；多个独立 worker 进程/副本可以依赖行锁并发领取不同任务，但当前 Makefile 默认只启动一个 worker，Docker Compose 默认不启动 worker。
- 队列可靠性：`GenerationRun` 已扩展 `queue_payload`、`queued_at`、`started_at`、`locked_at`、`locked_by`、`attempt_count`、`max_attempts`、`next_attempt_at`、`cancelled_at`。LLM 请求失败可按 `QUEUE_MAX_ATTEMPTS` 自动重试，格式/校验/配置类失败直接 failed；stale running 任务按 `QUEUE_STALE_AFTER_SECONDS` 恢复；仅 queued 任务可取消。已进入 `queued` 的任务如果长期无人领取，当前不会自动标记 failed 或告警，worker 恢复后会继续按 `created_at` 顺序领取。
- worker 可用性：worker 会写入 `generation_workers` 心跳；生成接口入队前会检查 `QUEUE_WORKER_HEARTBEAT_TIMEOUT_SECONDS` 时间窗口内是否有在线 worker，找不到时返回 503 且不创建 queued 任务。
- SSE 兼容接口：`POST /api/v1/projects/{project_id}/generate/{module}/stream` 已弃用并返回 410；前端应调用普通生成接口获取 `run_id`，轮询 `GET /api/v1/generation-runs/{run_id}`，完成后通过资源列表/详情接口读取保存结果。
- Blueprint 生成：`app/generators/blueprint_generator.py` 默认调用 LLM，读取 `Project.target_frontend_stack` 和 `Project.target_backend_stack`，输入最新 Requirement 和业务需求故事列表，输出经后端校验和规范化后保存到 `ProjectBlueprint.content`；deterministic helper 仅作为开发辅助保留。
- Project 技术栈：默认前端技术栈和后端技术栈统一定义在 `app/core/constants.py`，分别为 `DEFAULT_FRONTEND_STACK` 和 `DEFAULT_BACKEND_STACK`；`normalize_stack()` 会把 `None`、空字符串和全空白字符串兜底为默认值。`ProjectCreate` 和 `ProjectUpdate` 均支持 `target_frontend_stack`、`target_backend_stack`，PATCH 未传字段不改变原值，传空字符串会重置为默认值；`ProjectRead` 对历史空值也会返回默认值。
- 业务需求池：位于 Requirement 和 Blueprint 之间，`POST /projects/{project_id}/generate/business-stories` 会把最新或指定 Requirement 拆解为垂直切片故事，保存到 `business_requirement_stories` 并记录绑定 `requirement_id` 的 `GenerationRun`；`GET /projects/{project_id}/requirements` 会在每条需求响应中附带最新 `business_story_generation` 以及顶层 `progress_status/progress_label/progress_text`，`GET /requirements/{requirement_id}/business-story-generation` 可轮询单条需求最新生成状态；`PATCH /business-stories/{story_id}` 支持局部更新标题、优先级、状态、用户故事、业务范围、数据规则和验收标准，其中可编辑 JSON 字段在 service 层规范化后整体赋值保存；`DELETE /business-stories/{story_id}` 硬删除单条故事并返回 204；Blueprint 生成时若已有业务故事，会把精简故事列表写入 `content.business_requirement_stories`。
- 用户需求历史进度文案：Requirement 响应顶层 `progress_status` 固定为 `in_progress`、`success`、`failed` 三种之一；`progress_label` 固定为“进行中”“成功”“失败”；`progress_text` 固定为“正在更新”“更新成功”“更新失败”，不带中文句号。无业务故事生成记录时按同步创建完成处理为 `success`；`pending/queued/running/processing` 映射为 `in_progress`，`completed/succeeded/success` 映射为 `success`，`failed/error` 及未知终止状态映射为 `failed`。`business_story_generation.message` 继续保留原有技术/模块进度提示兼容行为；保留 `/generate/...` 路径、`run_type="generate_business_requirement_stories"` 和 `GenerationRun` 等技术标识不变。
- 响应约定：核心接口按任务定义直接返回资源本体或列表，不使用旧 `ApiResponse` 包装。
- 项目列表：`GET /api/v1/projects` 支持可选 `q` 参数，service layer 对 `q` 做 trim，非空时按 `Project.name.ilike("%q%")` 大小写不敏感模糊搜索，结果仍按 `created_at desc` 排序。
- 项目名称：`Project.name` 在 service layer 创建和更新时会 trim，trim 后为空返回 400；完全相同名称返回 409；数据库通过普通 unique 约束兜底，当前唯一性大小写敏感但忽略首尾空格。
- 项目描述：`ProjectCreate.description` 为可选字段；创建项目时前端可以只传 `name`，响应 `ProjectRead` 仍保留 `description` 字段，未传时为 `null`。
- 删除策略：`DELETE /api/v1/projects/{project_id}` 在 `ProjectService.delete_project` 中执行，删除失败会 rollback；Requirement、Blueprint、GenerationRun、BusinessRequirementStory 和结构化草案表通过既有 `ondelete="CASCADE"` 外键和 relationship cascade 清理。`DELETE /api/v1/business-stories/{story_id}` 在 `BusinessRequirementStoryService.delete_story` 中硬删除单条故事，删除失败会 rollback，不影响项目、需求、蓝图或其他故事。
- JSON 约定：模型层使用 `JSON().with_variant(JSONB, "postgresql")`，当前运行和测试都走 PostgreSQL JSONB。
- CORS：只读取 `BACKEND_CORS_ORIGINS`，逗号分隔。
- Auth：`/api/v1/auth/email-verification-codes`、`/register`、`/login` 为公开入口；登录成功通过 `access_token` HttpOnly Cookie 保存 7 天 JWT，登出清除 Cookie；`/auth/me` 和 `/auth/me` PATCH 返回/修改当前用户资料，不返回密码 hash、验证码或 token。密码使用 `bcrypt` hash，验证码只保存 HMAC-SHA256 hash。
- 权限：除 health 和 auth 公开入口外，业务接口默认要求登录。普通用户只能访问自己的 `Project` 及其下游 Requirement、BusinessRequirementStory、Blueprint、ApiContractDraft、DbModelDraft、ContextPack、GenerationRun；admin 可访问普通业务全局资源，但 admin 管理接口只允许管理非 admin 用户，不能提升其他用户为 admin。
- 多租户项目：`projects.owner_user_id` 指向 `users.id`；`Project.name` 唯一性改为同一 owner 内唯一，迁移会创建/查找 bootstrap admin 并把历史项目归属到该用户。

## Key Files and Directories

- `app/models/`: `Project`、`Requirement`、`BusinessRequirementStory`、`ProjectBlueprint`、`GenerationRun`、`ApiContractDraft`、`DbModelDraft`、`ContextPack` ORM 模型。
- `app/models/user.py`、`app/models/email_verification_code.py`: 用户和邮箱验证码 ORM 模型。
- `app/core/security.py`: bcrypt 密码 hash/verify、验证码 hash/verify、JWT encode/decode、密码强度校验和 avatar seed/color helper。
- `app/core/constants.py`: 全局默认技术栈常量和技术栈空值规范化 helper。
- `app/schemas/`: 各资源的 request/response Pydantic schema，response schema 使用 `from_attributes=True`。
- `app/api/v1/endpoints/`: health、projects、requirements、business_requirement_stories、blueprints、generation、api_contracts、db_models、context_packs、consistency routes。
- `app/services/`: Project/Requirement/BusinessRequirementStory/BusinessStoryGeneration/Blueprint/Generation 以及 API contract、DB model、Context Pack、一致性检查服务；项目列表搜索和删除事务边界位于 `ProjectService`。
- `app/services/llm_generation_runtime.py`: 后端内部 LLM stream 聚合工具，负责调用 `OpenAICompatibleLLMClient.stream()` 并拼接完整 raw text。
- `app/services/streaming_generation_service.py`: 四类 LLM 生成的共享执行层，负责调用内部流式聚合、JSON 解析、结构校验、资源保存、错误映射和更新已有 `GenerationRun`。
- `app/services/generation_queue_service.py`: PostgreSQL-backed 轻量队列服务，负责入队、领取、执行、重试/失败、取消 queued 任务和恢复 stale running 任务。
- `app/workers/generation_worker.py`: 独立后台 worker 入口。
- `app/generators/`: blueprint、API contract、DB model、Context Pack 生成入口；blueprint、API contract、DB model 默认调用真实 LLM 并做结构校验和规范化；consistency checker 仍为本地规则检查。
- `app/llm/json_client.py`: JSON 清洗和解析工具，兼容纯 JSON、Markdown fenced JSON 和前后少量解释文本；旧非流式调用入口仍存在，但四个主生成接口不再依赖它发起 LLM 请求。
- `app/prompts/business_story_decomposer.py`: 业务需求故事分解 system prompt 和 user payload builder，约束严格 JSON、垂直切片、优先级定义和禁止事项。
- `app/prompts/blueprint_generator.py`、`app/prompts/api_contract_generator.py`、`app/prompts/db_model_generator.py`: 三类结构化草案的 system prompt 和 user payload builder。
- `alembic/versions/20260708_0002_create_orchestrator_tables.py`: 创建第一批核心业务表。
- `alembic/versions/20260708_0003_create_structured_draft_tables.py`: 创建第二批结构化草案表。
- `alembic/versions/20260709_0004_add_unique_constraint_to_project_name.py`: 为 `projects.name` 添加普通唯一约束。
- `alembic/versions/20260710_0005_create_business_requirement_stories.py`: 创建业务需求故事池表和索引。
- `alembic/versions/20260711_0006_add_generation_run_progress.py`: 为 `generation_runs` 增加 `requirement_id`、`progress`、`message`，支持前端刷新后恢复业务故事生成进度。
- `alembic/versions/20260712_0009_add_users_and_project_ownership.py`: 创建 `users`、`email_verification_codes`，为 `projects` 增加 owner 外键并把项目名唯一性改为 `owner_user_id + name`；历史项目 owner 回填使用 PostgreSQL UUID 类型绑定，避免 UUID 列与 VARCHAR 参数类型不匹配。
- `tests/`: 使用本机 PostgreSQL 测试库验证 API、生成链路和 cascade 行为；`tests/conftest.py` 默认读取 `TEST_DATABASE_URL`，并拒绝非 PostgreSQL 或非 `_test` 数据库。

## Setup and Runbook

项目只使用根目录单个 `.env`，保留 `.env.example` 作为唯一配置模板；模板中每个环境变量上一行都有中文注释说明用途：

```bash
cp .env.example .env
```

`.env.example` 模板：

```env
APP_NAME=Fullstack Context Orchestrator API
BACKEND_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
DATABASE_URL=postgresql+psycopg://llh@localhost:5432/context_orchestrator
TEST_DATABASE_URL=postgresql+psycopg://llh@localhost:5432/context_orchestrator_test
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=replace-with-your-api-key
LLM_MODEL=qwen-plus
LLM_TIMEOUT_SECONDS=60
LLM_THINKING=false
QUEUE_WORKER_CONCURRENCY=1
QUEUE_POLL_INTERVAL_SECONDS=2
QUEUE_STALE_AFTER_SECONDS=900
QUEUE_WORKER_HEARTBEAT_TIMEOUT_SECONDS=15
QUEUE_MAX_ATTEMPTS=3
AUTH_SECRET_KEY=replace-with-a-long-random-secret
AUTH_TOKEN_EXPIRE_DAYS=7
AUTH_COOKIE_NAME=access_token
AUTH_COOKIE_SECURE=false
AUTH_COOKIE_SAMESITE=lax
EMAIL_VERIFICATION_EXPIRE_MINUTES=10
EMAIL_VERIFICATION_RESEND_SECONDS=60
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=
SMTP_USE_TLS=true
BOOTSTRAP_ADMIN_EMAIL=admin@example.com
BOOTSTRAP_ADMIN_USERNAME=admin
BOOTSTRAP_ADMIN_PASSWORD=Admin123!
```

常用命令：

```bash
uv sync
uv sync --group dev
uv run python -m alembic upgrade head
uv run python -m uvicorn app.main:app --reload
uv run python -m app.workers.generation_worker
uv run python -m ruff check .
uv run python -m pytest
```

Makefile 快捷命令：

```bash
make run
make worker
make dev-all
```

`make worker` 单独启动后台生成 worker；`make dev-all` 先执行 migration，再在同一 shell 中后台启动 worker，并以前台方式启动 FastAPI reload 服务，退出时会清理 worker 子进程。

本机 PostgreSQL：

```bash
brew services start postgresql@14
createdb context_orchestrator
createdb context_orchestrator_test
uv run python -m alembic upgrade head
```

Docker API 容器默认通过 `host.docker.internal:5432` 连接宿主机 PostgreSQL：

```bash
docker compose up api
```

Compose 内置 PostgreSQL 服务仅作为可选辅助本地数据库保留，需要显式启用 profile：`docker compose --profile local-db up -d db`。

## Testing and Verification

当前验证结果：

- `uv run python -m ruff check .` 通过。
- `uv run python -m pytest` 通过，84 个测试全部通过。
- `uv run python -m alembic upgrade head` 最近一次手动迁移验证到 `20260712_0009`，用户系统和项目 owner 迁移已在本机 PostgreSQL 通过。
- 当前环境中 `uv run <console-script>` 可能出现 spawn 失败，因此 Makefile 使用 `uv run python -m ...` 调用 alembic、uvicorn、ruff 和 pytest。
- 当前仓库 `.venv/bin/pytest` console script 的 shebang 仍指向旧目录，测试时可直接使用 `.venv/bin/python -m pytest`。
- pytest 默认连接 `context_orchestrator_test`，每个测试通过 `Base.metadata.create_all/drop_all` 隔离表结构和数据；测试不会自动创建或删除数据库本身。

测试覆盖：

- health 响应。
- Project CRUD、404。
- Project 创建不要求 `description`；创建和更新项目名会 trim；空白或 null 项目名返回 400；重复项目名返回 409。
- Project 创建和 PATCH 支持 `target_frontend_stack`、`target_backend_stack`；未传技术栈使用默认值，PATCH 未传不改变原值，空字符串重置为默认值，历史空字符串响应时兜底为默认值。
- Project 列表支持 `q` 按名称大小写不敏感模糊搜索，空白 `q` 等同于不搜索。
- Requirement 创建和按项目倒序列表；Requirement 响应包含 `business_story_generation`，无生成任务时为 `null`；同时包含顶层 `progress_status/progress_label/progress_text`，供前端控制需求历史卡片、输入框和重试按钮状态。
- 无需求生成 blueprint 返回 400，并记录 failed `GenerationRun`。
- 有需求生成 blueprint、列表和详情查询；blueprint content 包含 `tech_stack.frontend/backend`；当前按阶段要求始终走 deterministic mock。
- Blueprint prompt、`GenerationRun.input_snapshot` 和保存后的 `content.project.tech_stack` 使用项目当前保存的 `target_frontend_stack`、`target_backend_stack`；历史空值按默认技术栈兜底。
- 业务需求故事生成覆盖 Project/Requirement 缺失、无效 `requirement_id` 400、LLM 未配置 503、合法 LLM JSON 保存、非法输出 502、0 条故事失败、`overwrite=false` 追加、`overwrite=true` 重建、列表过滤、详情、PATCH 局部更新、可编辑 JSON 字段规范化、非法格式、单条 DELETE 删除、删除不存在 404、`GenerationRun` succeeded/failed 进度记录和最新状态查询。
- 后台队列测试覆盖 worker 未启动 503、入队、查询、取消 queued、领取最早任务、`FOR UPDATE SKIP LOCKED` 防重复领取、五类生成任务 worker 执行、LLM 请求失败重试、非重试失败、stale running 恢复和 `/stream` 弃用。
- Blueprint 生成在项目已有业务需求故事时，会在 `content.business_requirement_stories` 中包含故事标题、优先级、状态和用户故事；无故事时保持原逻辑。
- Blueprint 生成器内部未知异常会记录 failed `GenerationRun`，并转换为中文可读 HTTP 500。
- 生成 API contract、DB model、Context Pack，支持列表、详情、role 过滤和 Markdown 导出；无 LLM 必填配置时走 deterministic fallback。
- Context Pack 可在缺少 API contract 或 DB model 时生成，并在 prompt 中标记缺失上下文。
- Consistency check 覆盖 warning 和 passed 状态。
- 删除 Project 后关联 Requirement、BusinessRequirementStory、GenerationRun 和第二批结构化草案 cascade 清理。
- 删除 Project 后项目详情和按项目访问 requirements、blueprints、api-contracts、db-models、context-packs 均返回 404，已删除关联资源详情不可再访问。
- 旧 auth/template_items 占位接口保持测试通过。
- Auth 测试覆盖登录 Cookie、`/auth/me` 安全响应、未登录业务接口 401、邮箱验证码注册成功和弱密码拒绝；测试 fixture 默认创建真实用户并通过登录拿 Cookie。
- 多租户测试覆盖用户内项目访问、项目 owner 写入、独立资源 ID 访问权限和删除项目后关联资源不可访问。

## Current Decisions and Conventions

- 新任务定义优先于旧 scaffold 定义；不保留旧环境变量兼容层。
- 新核心接口不使用旧 `ApiResponse` 包装。
- `ProjectBlueprint.content`、`GenerationRun` snapshots 和第二批 draft/context content 在应用和测试中都使用 PostgreSQL JSONB。
- `Project.name` 当前采用 `(owner_user_id, name)` 唯一约束，因此不同用户可以同名；同一用户内大小写敏感唯一，service layer 会先 trim 再查重，并捕获数据库 `IntegrityError` 转成业务 409。
- 用户角色固定为 `user`、`vip-plus`、`vip-pro`、`vip-pro-max`、`admin`；本批不做会员限流或功能差异化，所有非 admin 角色可使用同样普通功能。
- Admin 不可管理其他 admin，也不可把非 admin 用户提升为 admin；如未来需要超级管理员，需要新增独立权限模型。
- `GenerationRun` 是后台生成队列任务表，记录 `queued/running/completed/failed/cancelled` 状态；`generate_blueprint`、`generate_api_contract`、`generate_db_model`、`generate_context_packs` 和 `generate_business_requirement_stories` 都通过队列执行。
- `QUEUE_WORKER_ID` 是 worker 标识的可选覆盖项；未配置时 `run_worker_loop()` 自动生成 `hostname:id(object())`。普通开发和单实例部署不应要求手填该变量，避免在多 worker 复用环境中出现心跳记录和 `locked_by` 标识混淆。
- `GenerationRun` 成功状态统一写 `completed`；业务故事状态查询接口会把 `completed` 兼容映射为前端既有 `succeeded`。成功 `output_snapshot` 记录 `raw_text_length`、资源 id 或资源 id 列表、counts 和 summary；失败 `output_snapshot` 记录 `failure_stage` 和可选 `raw_text_length`，并保存 `error_message`。
- 业务需求故事优先级固定为 `p1_must`、`p2_should`、`p3_could`、`p4_wont`；状态固定为 `draft`、`ready`、`in_progress`、`done`、`deferred`，生成默认 `draft`。
- 业务需求故事 LLM 输出必须是 JSON object，顶层含非空 `stories` list；每个故事必须含 `title`、`priority`、`user_story`、`business_scope`、`data_rules`、`acceptance_criteria`，其中 `business_scope` 会规范化为 `included` 和 `excluded`。若未生成任何有效故事，生成任务失败并记录“未生成有效业务需求故事。”。
- 业务需求故事 PATCH 使用 `model_dump(exclude_unset=True)` 做局部更新；`user_story` 保存 trim 后非空字符串；`business_scope` 保存为 `{"included": list[str], "excluded": list[str]}`，缺失项补空数组；`data_rules` 允许 `{rule}` 或 `{field, rule}`，过滤空 rule；`acceptance_criteria` trim 并过滤空字符串。
- 业务需求故事生成会向 LLM 请求传入 `response_format={"type":"json_object"}`；主生成流程不再发起二次非流式 JSON 修复，解析或结构校验失败直接返回 502 并记录 failed `GenerationRun`。
- Blueprint、API contract 和 DB model 每次生成创建新记录，version 从 1 开始递增。
- `Project` ORM 技术栈字段为 `target_frontend_stack` 和 `target_backend_stack`；读取 ORM 对象时不要使用旧字段名 `frontend_stack` 或 `backend_stack`。默认值只能从 `app/core/constants.py` 引用，避免在 model、schema、service、prompt 或 generator 中重复硬编码。
- Context Pack 第一批固定生成 `frontend_engineer` 和 `backend_engineer` 两种角色。
- Markdown export 返回 JSON：`filename`、`content_type`、`content`，不返回文件流。
- LLM 输出必须是 JSON object；`app/llm/json_client.py` 会兼容去除外层 Markdown code fence 后解析 JSON。
- `POST /api/v1/projects/{project_id}/generate/blueprint`、`/api-contract`、`/db-model` 默认不再静默 fallback 到 deterministic 数据；生成接口成功入队返回 202，LLM 配置、请求、空输出、格式、校验和保存失败由 worker 写入 failed `GenerationRun`。
- 普通生成接口的业务前置错误（如项目、需求、蓝图缺失）仍使用普通 HTTP 4xx 且不创建 `GenerationRun`；入队后错误不再通过原 POST 响应返回，而是通过 `GET /api/v1/generation-runs/{run_id}` 查询状态和错误。
- LLM 请求不传入 `max_tokens` 或 `temperature`，项目侧不设置输出 token 上限和生成温度，相关行为交由模型服务默认策略处理。
- 当前 README、`.env.example` 和 `.env` 使用 DashScope OpenAI-compatible 示例：`https://dashscope.aliyuncs.com/compatible-mode/v1` + `qwen-plus`。

## Known Issues and Follow-ups

- 尚未实现超级管理员、审计日志、登录失败限流、密码重置、多用户协作、生产监控和会员功能限流。
- `AUTH_SECRET_KEY` 生产环境必须配置强随机值；默认开发 fallback 仅用于本地调试，不应上线使用。
- SMTP 未配置时验证码只写后端日志用于开发；生产环境需要配置 SMTP 并避免日志采集暴露验证码。
- 后台队列当前只自动恢复 stale `running` 任务；对长期 `queued` 等待任务尚无超时失败、告警、管理端重排或强制失败机制。
- `QUEUE_WORKER_CONCURRENCY` 当前未生效；如要单实例内并发执行，需要实现 worker pool/多进程启动并确保每个执行单元使用独立 SQLAlchemy `Session` 和唯一 `worker_id`。多 worker 并发部署还应评估同一项目多种生成任务同时写入最新资源时的业务竞态，必要时增加 project/module 级互斥或幂等约束。
- `running` 生成任务尚不支持提前终止；如需支持，需要增加协作式取消状态并在 worker 的 LLM 调用前后、解析前、保存前检查取消请求。
- Consistency check 当前只做基础结构一致性检查，后续可扩展为 schema/endpoint/DB 字段级别校验。
- Context Pack prompt 在真实运行时由 LLM 生成；测试 fallback 仍使用本地模板文案，后续可扩展为可配置模板和版本管理。
- Blueprint、API Contract、DB Model 已默认接入 LLM，测试通过 monkeypatch/mock `generate_json` 返回结构化 payload；真实模型环境仍需人工端到端验收。
- TestClient 当前有 StarletteDeprecationWarning，提示未来可能需要使用 `httpx2`。
- 如果已有数据库中存在完全相同的 `projects.name`，迁移 `20260709_0004` 会失败；上线前需要先清理历史重复数据。若未来要求大小写不敏感唯一，可改为 PostgreSQL functional unique index，如 `lower(name)`。
