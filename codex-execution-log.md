
## 2026-07-11 15:08 CST - 调整用户需求历史业务故事进度文案

- Request: 检查后端是否向“原始用户需求页面 / 用户需求历史 / 进度条”返回含“生成”的提示文案，并仅在相关范围内改为“更新”。
- Actions: 全局搜索 `生成`、`进度`、`用户需求`、`Requirement`、`progress`、`status`、`message`、`generation`、`GenerationRun` 等关键词，重点检查 `app/api/`、`app/services/`、`app/schemas/`、`app/models/`、`app/generators/`、`app/prompts/`、`app/core/`；确认 `RequirementRead.business_story_generation` 和单条状态接口会返回 `GenerationRun.message`；仅调整业务需求故事进度状态文案和对应测试断言。
- Result: 业务需求故事进度提示从“正在生成/已生成/生成失败/开始调用大模型生成/已生成 N 条”改为“正在更新/已更新/更新失败/开始调用大模型更新/已更新 N 条”；未修改 API 路径、函数名、`run_type`、`GenerationRun`、`generation_run_id` 或其他模块生成语义。
- Verification: `uv run python -m pytest tests/test_business_requirement_stories.py tests/test_streaming_generation.py` 通过，35 个测试全部通过；定向 `rg` 确认剩余“生成业务需求故事”均为错误原因、HTTP detail 或 LLM prompt，不属于用户需求历史进度条提示。

## 2026-07-08 13:06 CST - 实现上下文编排器第一批后端基础功能

- Request: 用户要求按新任务定义实现 FastAPI 后端第一批基础功能，不做旧契约兼容。
- Actions: 切换同步 SQLAlchemy `psycopg` 主路径，新增 Project/Requirement/ProjectBlueprint/GenerationRun 模型、schema、service、routes、mock blueprint generator、Alembic migration、env 示例、README、Docker 配置和测试。
- Result: 新核心 API 直接返回资源本体，支持项目 CRUD、需求提交/列表、blueprint 生成/列表/详情、GenerationRun 记录和 cascade 删除。
- Verification: `uv run ruff check .` 通过；`uv run python -m pytest` 通过，11 个测试全部通过。
- Follow-ups: 后续可接入真实 LLM、认证授权、多用户协作、生产监控和 httpx2 测试客户端迁移。

## 2026-07-08 13:10 CST - 修复 Makefile 的 uv console script 启动问题

- Request: 用户运行 `make dev` 时遇到 `uv run alembic` spawn 失败。
- Actions: 将 Makefile 和 README 中的 `uv run alembic`、`uv run uvicorn`、`uv run ruff` 改为 `uv run python -m ...`，并更新技术文档中的运行约定。
- Result: 项目命令不再依赖当前环境中会失败的 console script spawn 路径。
- Verification: `uv run python -m ruff check .` 通过；`uv run python -m pytest` 通过，11 个测试全部通过；`docker compose ps` 显示 Docker daemon 未运行。
- Follow-ups: 启动 Docker Desktop 后运行 `docker compose up -d db`，再执行 `make dev`。

## 2026-07-08 13:18 CST - 切换开发运行到本机 PostgreSQL

- Request: 用户要求使用本机数据库而不是 Docker。
- Actions: 检查 Homebrew PostgreSQL 状态，确认本机 `llh` 角色可用；创建 `context_orchestrator` 数据库；将 `.env` 切换为 `postgresql+psycopg://llh@localhost:5432/context_orchestrator`；运行 Alembic migration；更新 README 本机数据库说明。
- Result: 本机数据库已迁移到 `20260708_0002 (head)`，核心表已创建。
- Verification: `uv run python -m alembic upgrade head` 成功；`uv run python -m alembic current` 显示 head；`uv run python -m ruff check .` 通过。
- Follow-ups: 后端可直接通过 `make dev` 启动；若 PostgreSQL 未运行，先执行 `brew services start postgresql@14`。

## 2026-07-08 15:35 CST - 实现第二批结构化开发产物功能

- Request: 用户要求按既定计划实现 API 契约草案、数据库模型草案、Context Pack、一致性检查和 Markdown 导出。
- Actions: 新增 `ApiContractDraft`、`DbModelDraft`、`ContextPack` 模型、schema、generator、service、endpoint 和 Alembic migration；扩展 generation routes、router 聚合、Project 关系和 Blueprint latest helper；新增结构化草案端到端测试；更新 README 和技术文档。
- Result: 后端支持基于最新 ProjectBlueprint 生成 API contract、DB model、frontend/backend Context Pack，支持列表、详情、role 过滤、Markdown 导出、基础一致性检查和 GenerationRun 成功/失败记录。
- Verification: `uv run python -m ruff check .` 通过；`uv run python -m pytest` 通过，18 个测试全部通过；`uv run python -m alembic upgrade head` 成功升级到 `20260708_0003`。
- Follow-ups: 后续可扩展字段级一致性检查、Context Pack 模板版本管理、真实 LLM provider、认证授权和生产级监控。

## 2026-07-08 18:02 CST - 接入真实 LLM API 生成链路

- Request: 用户要求将当前项目中需要使用 LLM API 的位置改为调用真实 LLM API，并说明 `.env` 所需配置。
- Actions: 新增 `app/llm/json_client.py` 统一封装 `.venv` 中 `monobase.llm` 的 OpenAI-compatible JSON 调用；扩展 `Settings` 的 LLM 配置项；将 blueprint、API contract、DB model、Context Pack 生成器改为有配置时调用真实 LLM，测试环境无配置时保留 deterministic fallback；补齐 blueprint 生成失败的 `GenerationRun` 记录；更新 `.env.*.example` 和 README 配置说明。
- Result: 开发/生产环境的生成接口默认要求配置 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL` 后调用真实模型，测试环境仍可稳定离线运行。
- Verification: `uv run python -m ruff check .` 通过；`uv run python -m pytest` 通过，18 个测试全部通过；轻量导入检查确认开发环境未配置 LLM 时会进入真实调用要求配置路径。
- Follow-ups: 使用真实密钥启动服务后，可通过生成接口做一次端到端人工验收，确认所选模型返回 JSON 质量满足结构要求。

## 2026-07-08 18:15 CST - 收敛为单一 `.env` 配置

- Request: 用户要求当前项目无需区分开发、测试、生产环境，直接使用单个 `.env`。
- Actions: 移除 `APP_ENV` 配置项和日志中的环境分支；删除 `.env.dev.example`、`.env.example`、`.env.prod.example`、`.env.test.example`；整理根目录 `.env` 为唯一配置文件；更新 Docker Compose、README 和技术文档；将 LLM fallback 判断改为只看 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL` 是否配置。
- Result: 项目运行配置统一为根目录 `.env`，不再维护多环境示例或依赖 `APP_ENV`。
- Verification: `uv run python -m ruff check .` 通过；`uv run python -m pytest` 通过，18 个测试全部通过；配置加载检查确认 `settings` 不再包含 `app_env`。
- Follow-ups: 若需要真实 LLM 生成，直接在 `.env` 中填写并启用 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`。

## 2026-07-08 18:22 CST - 移除 LLM 输出 token 上限配置

- Request: 用户要求去除 `LLM_MAX_TOKENS` 限制，改为无限制。
- Actions: 从 `Settings`、`app/llm/json_client.py`、README、技术文档和根目录 `.env` 中移除 `LLM_MAX_TOKENS`；LLM 请求不再向 `monobase.llm.LLMConfig` 传入 `max_tokens`。
- Result: 项目侧不再设置 LLM 输出 token 上限，输出长度交由模型服务默认策略处理。
- Verification: `uv run python -m ruff check .` 通过；`uv run python -m pytest` 通过，18 个测试全部通过；配置加载检查确认 `settings` 不再包含 `llm_max_tokens`。
- Follow-ups: 如果模型服务自身有默认输出上限，需要在服务商控制台或模型参数能力范围内处理。

## 2026-07-08 18:45 CST - 恢复单一 `.env.example` 模板

- Request: 用户要求保留 `.env.example`。
- Actions: 恢复 `.env.example` 作为单一 `.env` 配置模板；保持删除 dev/prod/test 多环境示例；确认模板不包含 `LLM_MAX_TOKENS`；更新 README 和技术文档中的复制说明。
- Result: 项目继续只使用根目录 `.env`，同时保留 `.env.example` 便于初始化配置。
- Verification: `uv run python -m ruff check .` 通过；`uv run python -m pytest` 通过，18 个测试全部通过；搜索确认无 `LLM_MAX_TOKENS` 和多环境示例引用。
- Follow-ups: 无。

## 2026-07-08 18:52 CST - 移除 LLM 温度配置

- Request: 用户要求去除 `LLM_TEMPERATURE`，改为默认不配置。
- Actions: 从 `Settings`、`app/llm/json_client.py`、`.env`、`.env.example`、README 和技术文档中移除 `LLM_TEMPERATURE`；LLM 请求不再向 `monobase.llm.LLMConfig` 传入 `temperature`。
- Result: 项目侧不再设置 LLM 生成温度，温度策略交由模型服务默认值处理。
- Verification: `uv run python -m ruff check .` 通过；`uv run python -m pytest` 通过，18 个测试全部通过；配置加载检查确认 `settings` 不再包含 `llm_temperature`。
- Follow-ups: 无。

## 2026-07-11 00:26 CST - 三类结构化草案默认接入 LLM 生成

- Request: 用户要求执行此前评估，把 Project Blueprint、API Contract Draft、Db Model Draft 三个模块升级为真实 LLM generator。
- Actions: 新增 `app/prompts/blueprint_generator.py`、`app/prompts/api_contract_generator.py`、`app/prompts/db_model_generator.py`；改造三个 generator 的 LLM 调用、结构校验和规范化；改造 `GenerationService`、`ApiContractService`、`DbModelService` 的 running/completed/failed `GenerationRun` 记录和 503/502 错误映射；更新测试使用 mock LLM JSON 覆盖成功、配置缺失和格式错误。
- Result: 三个生成接口默认调用 LLM，不再静默 fallback 到 deterministic 数据；LLM 未配置返回 503，LLM 请求失败或结构化输出错误返回 502；成功和失败均记录 `GenerationRun`；DB Model 会纳入最新 API Contract 作为可选上下文。
- Verification: `uv run python -m ruff check .` 通过；`uv run python -m pytest -q` 通过，52 个测试全部通过。
- Follow-ups: 真实模型环境仍需按 `.env` 配置后做一次手动端到端验收；deterministic helper 仍保留为开发辅助函数，但默认生成路径不使用。

## 2026-07-11 00:15 CST - 评估三类结构化草案 LLM 化任务

- Request: 用户要求全面深度评估把 Project Blueprint、API Contract Draft、Db Model Draft 三个生成模块升级为真实 LLM generator 的当前任务。
- Actions: 阅读用户任务说明，检查 `app/services/generation_service.py`、三个 draft service/generator、`app/llm/client.py`、`app/llm/json_client.py`、配置、schema、endpoint、测试和现有项目技术文档。
- Result: 确认当前业务故事生成已有可复用的 LLM 错误映射和 `GenerationRun` 模板；Blueprint 仍为 deterministic mock；API contract 和 DB model 只有薄 LLM 分支，缺少 prompt 文件、结构校验、服务层 503/502 映射和完整 running/failed 记录；测试默认依赖无 LLM fallback，需要同步改造。
- Verification: 静态阅读和 `rg` 搜索；未运行测试，因为本次未修改业务代码。
- Follow-ups: 实施时应优先抽取通用 LLM 结构化生成错误处理/校验工具，再逐个迁移三个模块并补充 mock LLM 测试。

## 2026-07-09 11:50 CST - 增强项目搜索与删除级联验证

- Request: 用户要求 `GET /api/v1/projects` 支持按项目名称模糊搜索，并确保删除项目时清理所有关联内容且保持 API 兼容。
- Actions: 在 `ProjectService.list_projects` 中新增可选 `q` 参数、trim 和 `Project.name.ilike` 过滤；路由透传 query 参数；为 `delete_project` 增加失败 rollback；补充项目名称搜索和完整关联内容删除测试。
- Result: 项目列表无 `q` 时保持原行为，有 `q` 时按名称大小写不敏感模糊搜索；删除项目继续返回 204，并依赖现有 `ondelete="CASCADE"`/relationship cascade 清理 Requirement、Blueprint、API contract、DB model、Context Pack 和 GenerationRun。
- Verification: `uv run ruff check app/api/v1/endpoints/projects.py app/services/project_service.py tests/test_projects.py` 通过；`uv run python -m pytest` 通过，20 个测试全部通过。
- Follow-ups: 当前仅覆盖按项目名称搜索；如未来新增 Project 关联表，需要同步补充模型外键 cascade 和删除测试。

## 2026-07-09 14:06 CST - 修复蓝图生成项目技术栈字段访问

- Request: 用户要求修复 `POST /api/v1/projects/{project_id}/generate/blueprint` 因访问 `Project.frontend_stack` 导致的 500，并加固蓝图生成器和错误处理。
- Actions: 将 `app/generators/blueprint_generator.py` 改为读取 `target_frontend_stack`/`target_backend_stack`，新增 `build_deterministic_blueprint_content` 和安全 `getattr` fallback；在 `GenerationService` 中记录 failed `GenerationRun` 并将未知异常转换为可读 HTTP 500；补充蓝图生成成功、404、生成器异常转换测试。
- Result: 蓝图生成内容包含 `tech_stack.frontend/backend`，不再访问不存在的旧 ORM 字段；项目不存在仍返回 404，无需求仍返回 400，生成器内部异常会落库并返回中文错误。
- Verification: `uv run python -m pytest` 通过，22 个测试全部通过；搜索确认业务代码无 `project.frontend_stack`/`project.backend_stack` 访问。
- Follow-ups: `app/generators/context_pack_generator.py` 中的 `frontend_stack`/`backend_stack` 是输出 JSON 键名，不是 Project ORM 字段访问；如未来恢复 blueprint 真实 LLM，需要重新审查提示词和字段映射。

## 2026-07-09 19:16 CST - 项目名称唯一性和可选描述

- Request: 用户要求创建 Project 时 `description` 不再必填，`name` trim 后不能为空且不能重复，重复返回 409，并尽量补充数据库唯一约束和测试。
- Actions: 在 `Project.name` 上增加 ORM unique 标记和 Alembic migration `20260709_0004_add_unique_constraint_to_project_name.py`；在 `ProjectService` 中集中实现 name trim、空值 400、重复 409、`IntegrityError` 兜底转换；同步处理更新项目名重复、空白和 null；补充项目创建/更新测试。
- Result: `POST /api/v1/projects` 支持只传 `{"name": "项目名称"}`，保存 trim 后名称，响应仍包含 `description`；重复名称返回 `{"detail": "项目名称已存在，请使用其他名称。"}`。
- Verification: `uv run python -m ruff check app/models/project.py app/services/project_service.py tests/test_projects.py alembic/versions/20260709_0004_add_unique_constraint_to_project_name.py` 通过；`uv run python -m pytest tests/test_projects.py` 通过，12 个测试全部通过；`uv run python -m pytest` 通过，30 个测试全部通过。
- Follow-ups: 新增普通唯一约束大小写敏感；执行 migration 前若历史库存在完全相同的 `projects.name`，需先清理重复数据。

## 2026-07-10 00:00 CST - 实现业务需求池后端模块

- Request: 用户要求按评估计划实现业务需求故事池，包括模型、API、LLM 生成、校验、GenerationRun、蓝图集成和删除级联。
- Actions: 新增 `BusinessRequirementStory` ORM/schema/service/endpoint、OpenAI-compatible `httpx` LLM client、业务故事分解 prompt、Alembic migration `20260710_0005_create_business_requirement_stories.py` 和端到端测试；扩展 generation routes、Project/Requirement/GenerationRun 关系、模型聚合导入、README 和 `.env.example`；蓝图生成纳入已有业务故事上下文。
- Result: 后端支持生成、列表过滤、详情、PATCH 更新业务需求故事；LLM 未配置返回 503，LLM 请求或输出格式错误返回 502 并记录 failed `GenerationRun`；成功生成会保存故事并记录 completed `GenerationRun`；删除 Project 会级联删除业务故事。
- Verification: `uv run python -m ruff check .` 通过；`uv run python -m pytest` 通过，38 个测试全部通过。
- Follow-ups: 真实模型环境需按 `.env.example` 配置 `LLM_PROVIDER`、`LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`、`LLM_TIMEOUT_SECONDS` 后做一次人工端到端验收。

## 2026-07-10 17:44 CST - 修复业务故事生成 LLM 502

- Request: 用户要求评估并修复前端点击“生成业务需求故事”后接口返回 502 且提示 LLM 请求失败的问题。
- Actions: 排查 `/projects/{project_id}/generate/business-stories` 调用链，确认失败来自业务故事专用 `httpx` LLM client；将 `BusinessStoryGenerationService` 改为复用统一 `app/llm/json_client.py`，删除未引用的旧 `app/llm/client.py`，同步测试 mock 和 README/技术文档说明。
- Result: 业务故事生成不再单独强制 `response_format` 或手写 `/chat/completions` 请求路径，和 API contract、DB model、Context Pack 使用同一套 OpenAI-compatible JSON 调用封装；LLM 请求失败仍返回 502，LLM 输出格式不正确返回更明确的格式错误文案。
- Verification: `uv run python -m ruff check .` 通过；`uv run python -m pytest` 通过，38 个测试全部通过。
- Follow-ups: 使用真实 `.env` 密钥启动后端后，建议从前端对同一个项目重新点击生成，若仍失败，可查看 `generation_runs.error_message` 或后端日志中的供应商原始错误。

## 2026-07-10 17:53 CST - 加固业务故事 LLM JSON 输出

- Request: 用户反馈业务故事生成请求已返回 HTTP 200，但后端仍因 `LLM output is not valid JSON` 返回 502。
- Actions: 为统一 `generate_json` 增加 `extra_params` 支持和更具体的 JSON 解析错误；业务故事生成传入 `response_format={"type":"json_object"}`，并在首次 JSON 解析失败时带原始需求上下文发起一次严格 JSON 修复重试；强化业务故事 prompt 的严格 JSON 约束；补充响应格式参数和修复重试测试。
- Result: DashScope 返回非严格 JSON 时可自动重试修复；真实项目 `b1301fac-2e24-49e9-b9ab-571d56642878` 已成功生成 7 条业务故事，并记录 completed `GenerationRun`。
- Verification: `uv run python -m ruff check .` 通过；`uv run python -m pytest` 通过，40 个测试全部通过；真实服务层调用生成 7 条业务故事且落库。
- Follow-ups: 如果未来模型仍偶发输出异常，可在 `generation_runs.error_message` 查看更具体的 JSON 解析位置。

## 2026-07-10 18:01 CST - 确认 monobase 使用情况

- Request: 用户询问当前后端是否用到了 `monobase` 库的方法。
- Actions: 使用 `rg` 搜索 `monobase` 引用，查看 `app/llm/json_client.py`、`app/services/business_story_generation_service.py`、`pyproject.toml` 和现有技术文档。
- Result: 后端确实使用了 `monobase`：统一 LLM JSON 封装通过 `monobase.llm.LLMConfig`、`ModelType`、`LLMClientFactory.create(...).invoke(...)` 调用模型，并捕获 `ConfigurationError`、`LLMError`；多个生成器通过 `app.llm.json_client.generate_json` 间接使用该库。
- Verification: 静态代码搜索与文件阅读；未运行测试，因为本次仅做代码引用排查。

## 2026-07-11 15:55 CST - 评估轻量级后台消息队列方案

- Request: 用户要求评估当前后端如何实现轻量级后台消息队列。
- Actions: 检查 `GenerationRun` 模型、LLM 生成编排、API endpoint、数据库 session、配置和现有状态查询接口，评估 FastAPI BackgroundTasks、内存队列、Redis 队列和 PostgreSQL-backed queue 的取舍。
- Result: 推荐以 PostgreSQL + `GenerationRun` 扩展实现轻量持久化队列：接口只创建 queued run 并返回 202/run_id，独立 worker 使用 `FOR UPDATE SKIP LOCKED` 领取任务并复用现有生成执行链路；不推荐内存队列作为主方案。
- Verification: 静态代码阅读与架构评估；未运行测试，因为本次未修改业务代码。

## 2026-07-11 15:40 CST - 确认长耗时 LLM 任务执行方式

- Request: 用户询问当前后端中长耗时任务如大模型 API 调用是否会推送到消息队列中在后台排队运行。
- Actions: 搜索队列、worker、background task、Redis/Celery/RQ 等实现；检查 generation endpoint、`StreamingGenerationService`、`llm_generation_runtime`、`OpenAICompatibleLLMClient`、`pyproject.toml` 和 `docker-compose.yml`。
- Result: 当前没有消息队列、后台 worker 或 FastAPI `BackgroundTasks`；四类 LLM 生成接口会在 HTTP 请求生命周期内同步调用 LLM、聚合输出、解析校验、保存数据库并返回，`GenerationRun` 只是状态和进度记录，不代表队列任务。
- Verification: 静态代码检查与源码阅读；未运行测试，因为本次未修改业务代码。

## 2026-07-11 15:45 CST - 评估 PostgreSQL 轻量消息队列能力

- Request: 用户询问 PostgreSQL 是否自带当前项目可用的轻量级消息队列。
- Actions: 基于当前项目 PostgreSQL、SQLAlchemy、GenerationRun 进度记录和未接入独立 worker/Redis/Celery 的架构说明，分析 PostgreSQL 可作为轻量队列的实现方式和适用边界。
- Result: 确认 PostgreSQL 没有内置完整消息队列服务，但可用普通任务表配合 `FOR UPDATE SKIP LOCKED`、状态字段、重试字段和 worker 轮询实现项目可用的轻量任务队列；`LISTEN/NOTIFY` 可作为唤醒优化但不宜单独承载可靠队列。
- Verification: Not run；本次为架构问答，无代码改动。

## 2026-07-11 15:43 CST - 确认后端数据库配置

- Request: 用户询问当前后端使用的数据库是什么。
- Actions: 检查 `app/core/config.py`、`app/db/session.py`、`.env`、`docker-compose.yml`、Alembic migration 和项目技术文档中的数据库配置。
- Result: 确认运行时数据库为 PostgreSQL，连接串通过 `DATABASE_URL` 注入；本机 `.env` 指向 `postgresql+psycopg://llh@localhost:5432/context_orchestrator`，Docker 开发环境使用 `postgres:17-alpine`。
- Verification: Not run；本次为配置核查，无代码改动。

## 2026-07-10 20:22 CST - 增加业务需求故事单条删除接口

- Request: 用户要求实现 `DELETE /api/v1/business-stories/{story_id}`，供前端业务需求池故事卡片删除按钮使用。
- Actions: 在 `BusinessRequirementStoryService` 新增 `delete_story` 硬删除事务；在业务故事 endpoint 新增 204 DELETE 路由并声明 404 OpenAPI 响应；补充删除成功、删除不存在、只删除目标故事的测试；更新 README 接口清单。
- Result: 前端可按故事 ID 删除单条业务需求故事；删除成功无响应 body，后续项目业务故事列表不再返回被删除记录；不存在的故事返回 404。
- Verification: `uv run python -m pytest tests/test_business_requirement_stories.py` 通过，12 个测试全部通过；`uv run python -m pytest` 通过，42 个测试全部通过。
- Follow-ups: 当前认证模块仍是 scaffold，业务故事删除暂不做项目权限校验；未来接入权限后需按故事所属 `project_id` 增加校验。

## 2026-07-10 20:58 CST - 修复业务故事 service 冲突标记启动失败

- Request: 用户反馈 `make dev` 启动时报 `SyntaxError: invalid syntax`，文件中残留 `<<<<<<< ours`。
- Actions: 搜索并确认 `app/services/business_story_generation_service.py` 存在 Git 冲突标记；用无冲突的业务故事 LLM 稳定性实现覆盖该文件；修复 `app/llm/client.py` 行宽和 service import 排序；同步测试中的格式错误文案断言。
- Result: `app.main` 可正常导入，Uvicorn 可启动，业务故事生成测试恢复通过。
- Verification: `rg -n "<<<<<<<|=======|>>>>>>>" app tests README.md codex-execution-log.md codex-project-tech-doc.md` 无结果；`uv run python -m py_compile app/services/business_story_generation_service.py app/main.py` 通过；`uv run python -m ruff check .` 通过；`uv run python -m pytest -q` 通过，42 个测试全部通过；`uv run python -m uvicorn app.main:app --host 127.0.0.1 --port 8765` 成功启动并已关闭。

## 2026-07-10 21:07 CST - 增强业务故事 PATCH 局部更新

- Request: 用户要求按计划增强 `PATCH /api/v1/business-stories/{story_id}`，支持前端双击编辑用户故事、业务范围、数据规则和验收标准。
- Actions: 在 `BusinessRequirementStoryService.update_story` 中对 `user_story`、`business_scope`、`data_rules`、`acceptance_criteria` 做 service 层校验和规范化，并为 PATCH 局部更新、JSON 字段清洗和非法格式补充测试。
- Result: PATCH 继续使用 `exclude_unset=True` 保持局部更新；JSON 字段整体赋值保存；业务范围补齐 `included/excluded`，数组字段 trim 并过滤空字符串，非法格式返回可读 400 或 Pydantic 422。
- Verification: `uv run python -m pytest tests/test_business_requirement_stories.py` 通过，18 个测试全部通过；`uv run python -m pytest` 通过，48 个测试全部通过。
- Follow-ups: 当前非法 enum 仍由 Pydantic 422 处理；未来若需要统一错误 envelope，可在全局异常处理层调整。

## 2026-07-11 00:47 CST - 新增四类 LLM 流式生成接口

- Request: 用户要求按计划新增业务需求故事、蓝图、API 契约和数据库模型的 SSE 流式生成接口，同时保留现有非流式接口。
- Actions: 为 `OpenAICompatibleLLMClient` 增加 `stream()` 和 OpenAI-compatible SSE chunk 解析；新增 `StreamingGenerationService` 统一编排 `start/delta/raw_complete/parsed/saved/done/error` 事件、JSON 聚合解析、结构校验、资源保存和 `GenerationRun` 状态；在 generation routes 新增四个 `/stream` endpoint；补充流式 client 和路由测试。
- Result: 前端可通过 POST `text/event-stream` 实时接收 LLM delta，流式完成后收到保存后的正式资源；LLM 未配置、请求失败、空输出、格式错误和未知失败均返回明确 error 事件并记录 failed `GenerationRun`。
- Verification: `.venv/bin/python -m ruff check app tests/test_streaming_generation.py` 通过；`.venv/bin/python -m pytest tests/test_streaming_generation.py -q` 通过，7 个测试全部通过；`.venv/bin/python -m pytest -q` 通过，59 个测试全部通过。
- Follow-ups: 当前业务故事流式接口不展示 JSON 修复重试过程；如未来需要，可单独设计 repair 事件或二阶段修复流。

## 2026-07-11 11:03 CST - 兼容 DashScope 流式空 choices chunk

- Request: 用户反馈前端显示 LLM 结构化格式错误，后端日志显示 `llm.stream.invalid reason=empty_choices`。
- Actions: 调整 `extract_chat_completion_stream_delta`，将空 `choices` 和 usage-only chunk 视为可忽略 metadata；保留 provider error chunk 和非法类型 chunk 的错误处理；补充流式 chunk 解析回归断言。
- Result: DashScope 流式尾部统计或 metadata chunk 不再中断业务故事流式生成，最终内容仍由聚合 raw text 和 JSON 校验兜底。
- Verification: `.venv/bin/python -m ruff check app/llm/client.py tests/test_streaming_generation.py` 通过；`.venv/bin/python -m pytest tests/test_streaming_generation.py -q` 通过，7 个测试全部通过；`.venv/bin/python -m pytest -q` 通过，59 个测试全部通过。
- Follow-ups: 若供应商返回新的非 OpenAI-compatible chunk 形态，可在日志中保留安全 excerpt 后继续扩展 parser 兼容。

## 2026-07-11 11:40 CST - 持久化业务故事生成进度

- Request: 用户要求为保存原始用户需求后自动生成业务需求故事的前端流程，持久化生成任务状态、进度、说明和错误信息，并支持需求历史和轮询查询。
- Actions: 扩展 `GenerationRun` 增加 `requirement_id`、`progress`、`message` 和迁移 `20260711_0006_add_generation_run_progress.py`；业务故事同步和 SSE 生成均绑定 requirement 并更新 running/succeeded/failed 进度；Requirement 响应附带最新 `business_story_generation`；新增 `GET /api/v1/requirements/{requirement_id}/business-story-generation`；补充成功、LLM 未配置、无效 requirement、失败持久化、最新状态查询和 SSE 进度测试。
- Result: 前端刷新后可通过需求历史或轻量状态接口恢复最新业务故事生成状态；业务故事生成失败不会回滚已保存的原始用户需求；业务故事仍按原结构保存和列表展示。
- Verification: `uv run python -m ruff check .` 通过；`uv run python -m pytest -q` 通过，62 个测试全部通过。

## 2026-07-11 12:16 CST - 修复业务故事流式生成卡 25%

- Request: 用户要求排查并修复前端业务需求故事流式生成长期停留在 25%、列表无新故事的问题。
- Actions: 调整 `StreamingGenerationService` 的流式阶段进度为 `0/10/25/60/80/95/100`，在 LLM、解析、保存、完成和客户端断开阶段持久化状态并记录阶段日志；客户端断开时将 running run 标记为 failed；业务故事校验禁止空 `stories`；补充流式成功、空故事、保存失败、客户端断开、`overwrite=false` 追加和列表可见性测试。
- Result: 业务故事流式生成成功时先发送 `saved` 再发送 `done` 并以 `succeeded + 100` 结束；LLM 输出异常、0 条故事、保存失败或客户端断开都会写入 failed 和明确 `error_message`，不再永久停留在 running 25%。
- Verification: `uv run python -m pytest tests/test_streaming_generation.py tests/test_business_requirement_stories.py -q` 通过，33 个测试全部通过；`uv run python -m pytest -q` 通过，67 个测试全部通过；`uv run python -m ruff check app tests` 通过。

## 2026-07-11 13:22 CST - 改造普通生成接口为后端内部流式聚合

- Request: 用户要求按计划将四个普通 LLM 生成接口改为主流程：后端内部 `stream=true` 聚合，完成后解析、校验、保存并返回普通 JSON。
- Actions: 新增 `app/services/llm_generation_runtime.py` 聚合 LLM stream；重构 `StreamingGenerationService.generate()` 为四模块共享执行链路；普通 `/generate/business-stories`、`/blueprint`、`/api-contract`、`/db-model` 路由切换到内部流式聚合；SSE `/stream` 路由保留兼容但只发送 `start/saved/done/error` 状态事件；增强 stream chunk parser 兼容 `delta.content`、`message.content`、`text` 并跳过非法 JSON chunk；更新测试 mock 和断言。
- Result: 四个普通接口返回保存后的数据库资源 JSON，不再向前端输出 token delta；`GenerationRun` 成功统一写 `completed` 并记录 `raw_text_length`、资源 id、counts 和 summary，失败写入 `failure_stage` 与可选 raw 长度；业务故事状态接口继续兼容返回 `succeeded`。
- Verification: `uv run python -m pytest -q` 通过，69 个测试全部通过；`uv run ruff check .` 通过。`uv run pytest` 仍因 console script spawn 问题不可用，使用 `uv run python -m pytest`。
- Follow-ups: 若前端仍调用旧 SSE，需要确认它只依赖 `saved/done/error`，不再依赖 `delta`。
