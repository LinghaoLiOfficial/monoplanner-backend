# Project Technical Documentation

## Overview

本项目是 `Fullstack Context Orchestrator API` 后端，目标是把自然语言业务需求编排为业务需求故事池、分层变更集、版本化全栈设计资产和 Codex Prompt Pack。当前实现包含数据库、API、schema、service layer、Cookie/JWT 用户认证、多租户项目权限隔离、管理员用户管理、OpenAI-compatible 真实 LLM 生成链路、统一版本化设计资产存储与读取/手动更新接口，以及新的 Story -> 分层 ChangeSet -> 分层 Design Assets -> PromptPack 队列化编排主链路；`ProjectBlueprint` 仍保留历史兼容和只读摘要用途，但不再参与默认主编排。业务需求故事、分层 ChangeSet、API Contract Draft 和 Db Model Draft 生成均默认要求真实 LLM 配置，未配置时返回 503，不静默生成 mock 数据；LLM 请求失败或结构化输出错误返回 502 并记录 failed `GenerationRun`。LLM prompt 现在以 `app/prompts/templates/*/prompt.j2` 为运行时真实来源，每个模板同级保存对应 `output_schema.py` Pydantic schema，并统一使用 `===SYSTEM===` / `===USER===`、Input、Input Fields、Output Fields、Output Rules 和成对 Example 结构；schema 不再渲染进 prompt，而是通过 Instructor typed `response_model` 作为运行时结构契约，JSON 语法问题由 `json-repair` 做有限兜底。当前后端 LLM 的数据流改为：`business_story_decomposer` 维护当前业务故事池，`change_set` 按层产出一次性变更集，`backend_implementation` 对应后端工程实现语义，`blueprint_summary` 仅作为兼容能力，`prompt_pack` 再把各层新旧版本差异转成可执行指令。UI 视觉设计模板已升级为 `visual_system/layout_rules/component_style_rules` 主契约，前端工程实现模板已升级为 `route_definitions/directory_structure/code_logic/environment_variables/design_theme/dependencies` 主契约，API 契约模板已升级为 `api_base_path/api_resource_groups/endpoints/error_model` 主契约，后端工程实现模板已升级为 `directory_structure/code_logic/utility_classes/llm_interaction_templates/environment_variables/dependencies` 主契约，数据库模型模板已升级为 `database_tables/fields` 主契约，历史内容仍可兼容读取。

## Architecture

- Web 框架：FastAPI，统一 API 前缀为 `/api/v1`。
- 数据库：SQLAlchemy 2.x 同步 `Session`，所有运行入口统一使用宿主机本地 PostgreSQL；应用/Alembic 默认连接 `postgresql+psycopg://llh@localhost:5432/context_orchestrator`，测试默认连接 `postgresql+psycopg://llh@localhost:5432/context_orchestrator_test`。
- Migration：Alembic 读取 `app.db.base.Base.metadata`。
- 分层约定：endpoint 负责请求/响应和依赖注入，业务逻辑放在 `app/services/`，LLM 生成入口放在 `app/generators/`，统一 LLM JSON 调用封装放在 `app/llm/`。
- LLM 编排约定：`app/prompts/orchestration.py` 只负责把项目配置、故事快照、现有资产、变更集和版本差异拼成模板变量；真正的字段衔接关系由各阶段 service 决定。`GenerationQueueService` 负责入队和路由到 worker，`StreamingGenerationService` 负责 business-stories、blueprint、api-contract 和 db-model 的单任务结构化生成，`ChangeSetGenerationService` 负责 story -> change set，`DesignAssetOrchestrationService` 负责 change set -> 各层设计资产 -> prompt pack；新主链路已移除 `ProjectBlueprint` 作为中间编排节点，仅保留兼容读取和历史摘要。
- 配置：项目不区分开发、测试、生产环境，应用和 Alembic 读取根目录单个 `.env`；pytest 会把 `DATABASE_URL` 覆盖为 `TEST_DATABASE_URL`，并要求测试库名以 `_test` 结尾。
- 依赖与打包：`pyproject.toml` 不再声明外部 `monobase` 依赖，也不再通过 `[tool.uv.sources]` 指向 `monobase-0.1.0-py3-none-any.whl`；删除该 wheel 后必须同步刷新 `uv.lock`，避免 `uv run` 在生成 metadata 时继续读取不存在的本地 wheel。
- LLM：业务需求故事池和结构化生成器统一使用 `app/llm/client.py` 的 OpenAI-compatible Chat Completions；缺少 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL` 时返回 503，不生成 mock 数据。`OpenAICompatibleLLMClient` 支持 dict user payload 和已渲染 string user prompt；新模板链路会先通过 Jinja2 `StrictUndefined` 渲染 `.j2`，拆分出 system/user 两段再发送。真实配置完整时优先走 `app/llm/structured_client.py` 的 Instructor JSON mode typed generation，`LLM_STRUCTURED_MAX_RETRIES` 默认 `2`，成功后统一 `model_dump(mode="json")` 交给 service validator。`OpenAICompatibleLLMClient.stream()` 支持 OpenAI-compatible streaming chat completions，解析 `data: ...` SSE chunk 并产出 `choices[0].delta.content`、`choices[0].message.content` 或 `choices[0].text`；空 `choices`、usage-only chunk 和非法 JSON chunk 视为可忽略供应商 metadata，provider error chunk 仍抛错。流式请求使用独立 `LLM_STREAM_READ_TIMEOUT_SECONDS` 作为连续无数据读取超时，避免 ChangeSet apply 等长生成在已收到 HTTP 200 后因普通请求超时过短失败。若流式连接在返回部分文本后断开，编排 JSON 生成会先尝试解析已收到的完整 JSON；可解析则继续保存，不完整则保留为 `LLMRequestError` 进入队列重试。
- 后台生成队列：旧生成入口 `POST /api/v1/projects/{project_id}/generate/business-stories`、`/blueprint`、`/api-contract`、`/db-model`、`/context-packs` 和新版入口 `POST /api/v1/business-stories/{story_id}/execute`、`POST /api/v1/change-sets/{id}/apply`、`POST /api/v1/change-sets/{id}/regenerate`、`POST /api/v1/projects/{project_id}/prompt-packs/generate` 都只做业务前置校验并创建 `GenerationRun(status="queued")`，HTTP 返回 `202 Accepted` 和 `GenerationRunRead`；独立 worker 通过 `uv run python -m app.workers.generation_worker` 启动，使用 PostgreSQL `FOR UPDATE SKIP LOCKED` 领取任务并在后台执行 LLM/Context Pack/编排任务。`QUEUE_WORKER_CONCURRENCY` 当前真实控制单 worker 进程内的线程执行槽位数，默认 `1`；大于 `1` 时每个槽位使用独立 SQLAlchemy `Session` 和派生 `worker_id`，同一 project 下不同任务允许并发执行。Docker Compose 提供独立 `worker` service，复用 API 镜像并只运行后台 worker。worker 运行时会通过项目统一 logging 在控制台输出启动、slot 启动、任务领取、开始、完成、失败、重试、stale 恢复和进入空闲等待等状态。
- 队列可靠性：`GenerationRun` 已扩展 `queue_payload`、`queued_at`、`started_at`、`locked_at`、`locked_by`、`attempt_count`、`max_attempts`、`next_attempt_at`、`cancelled_at`。LLM 请求失败可按 `QUEUE_MAX_ATTEMPTS` 自动重试，格式/校验/配置类失败直接 failed；`apply_change_set` 这类直接编排路径抛出的 `LLMRequestError` 也会被视为可重试。stale running 任务按 `QUEUE_STALE_AFTER_SECONDS` 恢复；仅 queued 任务可取消。已进入 `queued` 的任务如果长期无人领取，当前不会自动标记 failed 或告警，worker 恢复后会继续按 `created_at` 顺序领取。
- worker 可用性：worker 会写入 `generation_workers` 心跳；生成接口入队前会检查 `QUEUE_WORKER_HEARTBEAT_TIMEOUT_SECONDS` 时间窗口内是否有在线 worker，找不到时返回 503 且不创建 queued 任务。
- SSE 兼容接口：`POST /api/v1/projects/{project_id}/generate/{module}/stream` 已弃用并返回 410；前端应调用普通生成接口获取 `run_id`，轮询 `GET /api/v1/generation-runs/{run_id}`，完成后通过资源列表/详情接口读取保存结果。
- Blueprint 生成：`app/generators/blueprint_generator.py` 默认调用 LLM，读取 `Project.target_frontend_stack` 和 `Project.target_backend_stack`，输入最新 Requirement 和业务需求故事列表，输出经后端校验和规范化后保存到 `ProjectBlueprint.content`；deterministic helper 仅作为开发辅助保留。
- Project 技术栈：默认前端技术栈和后端技术栈统一定义在 `app/core/constants.py`，分别为 `DEFAULT_FRONTEND_STACK` 和 `DEFAULT_BACKEND_STACK`；`normalize_stack()` 会把 `None`、空字符串和全空白字符串兜底为默认值。`ProjectCreate` 和 `ProjectUpdate` 均支持 `target_frontend_stack`、`target_backend_stack`，PATCH 未传字段不改变原值，传空字符串会重置为默认值；`ProjectRead` 对历史空值也会返回默认值。
- Project 配置：`Project` 复用为项目配置模块，除名称、描述和目标技术栈外，新增 `global_constraints`、`coding_preferences`、`prompt_preferences` 三个 JSONB 数组字段；`GET/PATCH /api/v1/projects/{project_id}/configuration` 是正式接口，`/config` 保留为兼容别名。Project create/update/config PATCH 支持 `project_name`、`project_description`、`frontend_tech_stack`、`backend_tech_stack` 输入别名，响应同时提供旧字段和新语义镜像字段。
- 业务需求池：位于 Requirement 和 Blueprint 之间，`POST /projects/{project_id}/generate/business-stories` 会把最新或指定 Requirement 拆解为垂直切片故事，保存到 `business_requirement_stories` 并记录绑定 `requirement_id` 的 `GenerationRun`；`GET /projects/{project_id}/requirements` 会在每条需求响应中附带最新 `business_story_generation` 以及顶层 `progress_status/progress_label/progress_text`，`GET /requirements/{requirement_id}/business-story-generation` 可轮询单条需求最新生成状态；`PATCH /business-stories/{story_id}` 支持局部更新标题、优先级、状态、用户故事、业务范围、数据规则和验收标准，其中可编辑 JSON 字段在 service 层规范化后整体赋值保存；`DELETE /business-stories/{story_id}` 硬删除单条故事并返回 204；Blueprint 生成时若已有业务故事，会把精简故事列表写入 `content.business_requirement_stories`。
- 统一设计资产：已新增 `ChangeSet`、`UXDesign`、`UIDesign`、`FrontendPageStructure`、`FrontendTooling`、`BackendServiceDesign`、`BackendTooling`，并给现有 `ProjectBlueprint`、`ApiContractDraft`、`DbModelDraft`、`ContextPack` 补齐 `source_requirement_id`、`source_story_id`、`change_set_id`、`generation_run_id`、`diff_from_previous` 等版本化来源字段；`ContextPack` 新增 `version`。`FrontendImplementation` 是 `FrontendPageStructure` 的语义别名，`BackendImplementation` 是 `BackendServiceDesign` 的语义别名；新路由 `/frontend-implementations` 和 `/backend-implementations` 与旧路由读写同一历史表。设计资产 PATCH、ChangeSet PATCH 和 ContextPack PATCH 现在都会创建下一版本记录并返回新 id，不原地覆盖；`diff_from_previous` 会在缺省时标准化为 `added/modified/removed`。`ui_designs.content` 仍是 JSONB，不迁移历史内容；新生成 UI 资产通过新版 `UIDesignOutput` 校验。`frontend_page_structures.content` 也保持 JSONB，不迁移历史内容；新生成前端工程实现资产通过新版 `FrontendPagesOutput` 校验，内部 layer/API 名 `frontend_pages` 仅保留兼容。`backend_service_designs.content` 也保持 JSONB，不迁移历史内容；新生成后端工程实现资产通过新版 `BackendImplementationOutput` 校验，内部 layer/API 名 `backend_services` 仅保留兼容。`api_contract_drafts.content` 继续保持 JSONB，不迁移历史内容；新生成 API 契约通过新版 `ApiContractOutput` 校验，`ApiContractDraft.base_path` 列从 `content.api_base_path` 镜像保存并兼容旧 `base_path`。`db_model_drafts.content` 继续保持 JSONB，不迁移历史内容；新生成数据库模型通过新版 `DbModelOutput` 校验，内部 `database_tables` 是主输出结构，旧 `entities` 仅保留兼容。
- 新版编排链路：`business-stories/{story_id}/execute` 创建 `generate_change_set` run，worker 调用 `ChangeSetGenerationService` 按 `ux_design`、`ui_design`、`frontend_pages`、`api_contract`、`backend_services`、`database_models` 的固定顺序为命中的 layer 生成同一 `batch_id` 下的分层 ChangeSet；`change-sets/{id}/apply` 创建 `apply_change_set` run，worker 调用 `DesignAssetOrchestrationService` 按同一固定顺序逐资产生成新版本资产，随后直接生成 `role="prompt_pack"` 的 ContextPack，不再生成新版 ProjectBlueprint；`prompt-packs/generate` 创建 `generate_prompt_pack` run，只生成 PromptPack，不修改设计资产。ChangeSet apply 会按 `project_id + change_set_id + layer` 复用已保存资产，支持 failed run 后再次点击或重试时跳过已完成 layer；PromptPack 同样按同一 ChangeSet 复用已生成的 `role="prompt_pack"`。
- 用户需求历史进度文案：Requirement 响应顶层 `progress_status` 固定为 `in_progress`、`success`、`failed` 三种之一；`progress_label` 固定为“进行中”“成功”“失败”；`progress_text` 固定为“正在更新”“更新成功”“更新失败”，不带中文句号。无业务故事生成记录时按同步创建完成处理为 `success`；`pending/queued/running/processing` 映射为 `in_progress`，`completed/succeeded/success` 映射为 `success`，`failed/error` 及未知终止状态映射为 `failed`。`business_story_generation.message` 继续保留原有技术/模块进度提示兼容行为；保留 `/generate/...` 路径、`run_type="generate_business_requirement_stories"` 和 `GenerationRun` 等技术标识不变。
- 响应约定：核心接口按任务定义直接返回资源本体或列表，不使用旧 `ApiResponse` 包装。
- 项目列表：`GET /api/v1/projects` 支持可选 `q` 参数，service layer 对 `q` 做 trim，非空时按 `Project.name.ilike("%q%")` 大小写不敏感模糊搜索，结果仍按 `created_at desc` 排序。
- 项目名称：`Project.name` 在 service layer 创建和更新时会 trim，trim 后为空返回 400；完全相同名称返回 409；数据库通过普通 unique 约束兜底，当前唯一性大小写敏感但忽略首尾空格。
- 项目描述：`ProjectCreate.description` 为可选字段；创建项目时前端可以只传 `name`，响应 `ProjectRead` 仍保留 `description` 字段，未传时为 `null`。
- 删除策略：`DELETE /api/v1/projects/{project_id}` 在 `ProjectService.delete_project` 中执行，删除失败会 rollback；Requirement、Blueprint、GenerationRun、BusinessRequirementStory 和结构化草案表通过既有 `ondelete="CASCADE"` 外键和 relationship cascade 清理。`DELETE /api/v1/business-stories/{story_id}` 在 `BusinessRequirementStoryService.delete_story` 中硬删除单条故事，删除失败会 rollback，不影响项目、需求、蓝图或其他故事。
- JSON 约定：模型层使用 `JSON().with_variant(JSONB, "postgresql")`，当前运行和测试都走 PostgreSQL JSONB。
- CORS：只读取 `BACKEND_CORS_ORIGINS`，逗号分隔。
- Auth：`/api/v1/auth/email-verification-codes`、`/api/v1/auth/register/code`（验证码发送兼容别名）、`/api/v1/auth/register`、`/api/v1/auth/login` 为公开入口；注册请求仍包含 `email`、`username`、`password`、`verification_code`，但登录请求只接受 `email` 和 `password`，会 trim/lowercase email 后按 `users.email` 查询用户，用户名不再作为登录凭证；登录成功通过 `access_token` HttpOnly Cookie 保存 7 天 JWT，登出清除 Cookie；`/api/v1/auth/me` 和 `/api/v1/auth/me` PATCH 返回/修改当前用户资料，不返回密码 hash、验证码或 token。密码使用 `bcrypt` hash，验证码只保存 HMAC-SHA256 hash。
- 权限：除 health 和 auth 公开入口外，业务接口默认要求登录。普通用户只能访问自己的 `Project` 及其下游 Requirement、BusinessRequirementStory、Blueprint、ApiContractDraft、DbModelDraft、ContextPack、GenerationRun；admin 可访问普通业务全局资源，但 admin 管理接口只允许管理非 admin 用户，不能提升其他用户为 admin。
- 多租户项目：`projects.owner_user_id` 指向 `users.id`；`Project.name` 唯一性改为同一 owner 内唯一，迁移会创建/查找 bootstrap admin 并把历史项目归属到该用户。

## Key Files and Directories

- `app/models/`: `Project`、`Requirement`、`BusinessRequirementStory`、`ChangeSet`、`UXDesign`、`UIDesign`、`FrontendPageStructure`、`FrontendTooling`、`ApiContractDraft`、`BackendServiceDesign`、`BackendTooling`、`DbModelDraft`、`ProjectBlueprint`、`ContextPack`、`GenerationRun` ORM 模型。
- `app/models/user.py`、`app/models/email_verification_code.py`: 用户和邮箱验证码 ORM 模型。
- `app/core/security.py`: bcrypt 密码 hash/verify、验证码 hash/verify、JWT encode/decode、密码强度校验和 avatar seed/color helper。
- `app/core/constants.py`: 全局默认技术栈常量和技术栈空值规范化 helper。
- `app/schemas/`: 各资源的 request/response Pydantic schema，response schema 使用 `from_attributes=True`。
- `app/api/v1/endpoints/`: health、projects、requirements、business_requirement_stories、change_sets、ux_designs、ui_designs、frontend_page_structures、frontend_toolings、blueprints、generation、api_contracts、backend_service_designs、backend_toolings、db_models、context_packs、consistency routes。
- `app/services/`: Project/Requirement/BusinessRequirementStory/BusinessStoryGeneration/Blueprint/Generation 以及 API contract、DB model、Context Pack、一致性检查服务；项目列表搜索和删除事务边界位于 `ProjectService`。
- `app/services/llm_generation_runtime.py`: 后端内部 LLM stream 聚合工具，负责调用 `OpenAICompatibleLLMClient.stream()` 并拼接完整 raw text。
- `app/services/streaming_generation_service.py`: 四类 LLM 生成的共享执行层，负责调用内部流式聚合、JSON 解析、结构校验、资源保存、错误映射和更新已有 `GenerationRun`。
- `app/services/generation_queue_service.py`: PostgreSQL-backed 轻量队列服务，负责入队、领取、执行、重试/失败、取消 queued 任务和恢复 stale running 任务。
- `app/services/design_asset_service.py`: 通用设计资产读取和版本化 PATCH 服务，被新增资产模块及旧资产 PATCH 复用；PATCH 会克隆旧记录、递增 version 并返回新记录。
- `app/services/versioning.py`: 版本化记录克隆和 `added/modified/removed` diff 计算 helper。
- `app/services/change_set_service.py`: ChangeSet 列表、详情、PATCH、apply/discard 的 Phase 1-2 服务。
- `app/services/change_set_generation_service.py`: Story execute 和 ChangeSet regenerate 的 LLM 变更集生成服务。
- `app/services/design_asset_orchestration_service.py`: ChangeSet apply 主编排服务，负责逐资产 LLM 生成、统一落库、蓝图总结和可选 prompt pack 生成。
- `app/services/prompt_pack_generation_service.py`: 显式 PromptPack 生成服务，也被 apply 编排复用。
- `app/services/orchestration_validators.py`、`app/services/orchestration_context.py`、`app/prompts/orchestration.py`: Phase 3-4 编排 prompt、上下文快照和输出校验。
- `app/workers/generation_worker.py`: 独立后台 worker 入口。
- `workers-standalone-summary.md`: 一句话说明当前后端 workers 单独运行入口与队列执行机制。
- `app/generators/`: blueprint、API contract、DB model、Context Pack 生成入口；blueprint、API contract、DB model 默认调用真实 LLM 并做结构校验和规范化；consistency checker 仍为本地规则检查。
- `app/llm/json_client.py`: JSON 清洗和解析工具，兼容纯 JSON、Markdown fenced JSON 和前后少量解释文本；严格解析失败后会使用 `json-repair` 做有限语法修复，仍要求顶层为 JSON object。
- `app/llm/structured_client.py`: Instructor typed structured generation 主入口，统一处理 `response_model`、schema validation retry、Pydantic dump 和错误映射。
- `app/prompts/renderer.py`: Jinja2 prompt renderer，使用 `StrictUndefined` 和 `tojson_pretty` 过滤器，渲染后校验每个模板必须且只能包含一个 `===SYSTEM===` 和一个 `===USER===`。
- `app/prompts/`: 当前后端提示词模板集中目录；Python builder 只构造动态变量上下文，运行时通过 `build_*_prompt()` 渲染 `.j2` 后发送给 LLM，schema 由 LLM runtime 的 `response_model` 承担。
- `app/prompts/templates/`: 每种 LLM prompt 模板的人类可读且运行时真实来源目录，每个具体目录下放置 `prompt.j2` 和同级 `output_schema.py`；已覆盖 business story、blueprint、API contract、DB model、ChangeSet、通用/特化设计资产、blueprint summary、PromptPack 和 ContextPack。UI 视觉设计目录固定输出 `version_summary`、`visual_system`、`layout_rules`、`component_style_rules`、`diff`；前端工程实现目录固定输出 `version_summary`、`route_definitions`、`directory_structure`、`code_logic`、`environment_variables`、`design_theme`、`dependencies`、`diff`；后端工程实现目录固定输出 `version_summary`、`directory_structure`、`code_logic`、`utility_classes`、`llm_interaction_templates`、`environment_variables`、`dependencies`、`diff`；数据库模型目录固定输出 `database`、`database_tables`、`fields`、`relationships`、`indexes`、`migration_notes`；API 契约目录固定输出 `api_base_path`、`api_resource_groups`、`group_name`、`group_purpose`、`endpoints`、`request_schema`、`response_schema`、`error_model` 和 `error_case`。
- `app/prompts/templates/`: 每种 LLM prompt 模板的人类可读且运行时真实来源目录，每个具体目录下放置 `prompt.j2` 和同级 `output_schema.py`；已覆盖 business story、blueprint、API contract、DB model、ChangeSet、通用/特化设计资产、blueprint summary、PromptPack 和 ContextPack。UI 视觉设计目录固定输出 `version_summary`、`visual_system`、`layout_rules`、`component_style_rules`、`diff`；前端工程实现目录固定输出 `version_summary`、`route_definitions`、`directory_structure`、`code_logic`、`environment_variables`、`design_theme`、`dependencies`、`diff`；后端工程实现目录固定输出 `version_summary`、`directory_structure`、`code_logic`、`utility_classes`、`llm_interaction_templates`、`environment_variables`、`dependencies`、`diff`，内部 layer 语义仍沿用 `backend_services`；数据库模型目录固定输出 `database`、`database_tables`、`fields`、`relationships`、`indexes`、`migration_notes`；API 契约目录固定输出 `api_base_path`、`api_resource_groups`、`group_name`、`group_purpose`、`endpoints`、`request_schema`、`response_schema`、`error_model` 和 `error_case`。
- `docs/backend_llm_tasks_analysis.md`: 后端真实 LLM 任务的全链路分析文档，按 `prompt.j2` + `output_schema.py` 模板对逐一说明输入特征、输出字段、逻辑链、失败路径和 `ContextPack` 边界。
- `tests/test_prompt_template_contracts.py`: LLM 模板开发规则的主要回归测试；要求每个注册模板存在 `prompt.j2` 和 `output_schema.py`，包含唯一 `===SYSTEM===` / `===USER===`，USER 区包含同级小节 `Input:`、`Input Fields:`、`Output Fields:`、`Output Rules:`，其子项使用 `  - ` 缩进，Example Input/Output 编号成对，并能用最小变量上下文成功渲染为非空 system/user。
- `app/prompts/template_registry.py`: Prompt 模板目录、`prompt.j2`、`output_schema.py` 和 Pydantic response model 的索引表。
- `docs/llm-prompt-template-development-rules.md`: 面向后续实现者的 LLM 任务输入模板与输出结构检查开发规则，说明 `.j2` 运行时来源、固定章节、Example 成对、schema 第一真相、renderer 严格校验和测试要求。
- `llm-call-implementation-summary.md`: 面向人类阅读的 LLM 调用实现总结，概括普通 JSON 生成、编排型生成和流式聚合生成三类路径。
- `llm-structured-output-toolchain-summary.md`: 一句话总结当前后端 LLM 结构化输出工具链的构建方式，便于快速对照当前实现。
- `app/prompts/business_story_decomposer.py`: 业务需求故事分解模板变量 builder 和 `build_business_story_decomposition_prompt()` 运行时渲染入口。
- `app/prompts/templates/business_story_decomposer/prompt.j2` 与同级 `output_schema.py`: “原始用户需求 -> 敏捷业务需求”任务的运行时输入模板和目标输出 schema；服务层仍通过 `_validate_story_payloads()` / `_normalize_story()` 做最终结构检查和归一化。
- `app/prompts/blueprint_generator.py`、`app/prompts/api_contract_generator.py`、`app/prompts/db_model_generator.py`: 三类结构化草案的模板变量 builder 和 `.j2` 渲染入口。
- `alembic/versions/20260708_0002_create_orchestrator_tables.py`: 创建第一批核心业务表。
- `alembic/versions/20260708_0003_create_structured_draft_tables.py`: 创建第二批结构化草案表。
- `alembic/versions/20260709_0004_add_unique_constraint_to_project_name.py`: 为 `projects.name` 添加普通唯一约束。
- `alembic/versions/20260710_0005_create_business_requirement_stories.py`: 创建业务需求故事池表和索引。
- `alembic/versions/20260711_0006_add_generation_run_progress.py`: 为 `generation_runs` 增加 `requirement_id`、`progress`、`message`，支持前端刷新后恢复业务故事生成进度。
- `alembic/versions/20260712_0009_add_users_and_project_ownership.py`: 创建 `users`、`email_verification_codes`，为 `projects` 增加 owner 外键并把项目名唯一性改为 `owner_user_id + name`；历史项目 owner 回填使用 PostgreSQL UUID 类型绑定，避免 UUID 列与 VARCHAR 参数类型不匹配。
- `alembic/versions/20260714_0011_add_phase_1_2_design_assets.py`: Phase 1-2 迁移，新增 ChangeSet 和四个前后端设计资产表，扩展 Project 配置、BusinessRequirementStory 范围字段，以及现有设计资产统一来源/diff/version 字段。
- `alembic/versions/20260802_0012_add_ux_ui_design_assets.py`: 新增 `ux_designs`、`ui_designs` 两张版本化设计资产表，包含 project/source/change_set/generation_run 外键和索引，不回填或修改历史 `affected_layers`。
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
LLM_STREAM_READ_TIMEOUT_SECONDS=300
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
SMTP_HOST=smtp.qq.com
SMTP_PORT=465
SMTP_CODE=
SMTP_SENDER_EMAIL=
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
make workers
make dev-all
```

`make dev`、`make run`、`make workers` 等命令内部使用 `uv run python -m ...`。如果 shell 里激活了其他项目的虚拟环境，uv 会提示 `VIRTUAL_ENV=... does not match the project environment path .venv and will be ignored`；这表示 uv 忽略了外部虚拟环境并使用当前项目 `.venv`，通常不影响运行。消除提示的推荐做法是先 `deactivate`，或激活当前项目 `.venv`；只有确实想使用当前已激活环境时才使用 `uv run --active ...`。

`make workers` 单独启动后台生成 worker 并发池；`make dev-all` 先执行 migration，再在同一 shell 中后台启动 worker，并以前台方式启动 FastAPI reload 服务，退出时会清理 worker 子进程。worker 控制台日志使用 `generation.worker.*` 前缀展示启动、领取任务、执行结果、重试/失败和空闲等待状态。

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
- `make migrate` 在 2026-08-06 通过；`make dev` 在 2026-08-06 可成功启动 Uvicorn，不再因缺失 `monobase-0.1.0-py3-none-any.whl` 失败。
- `uv run python -c "import app.main; print('app import ok')"` 在 2026-08-06 通过。
- `uv run python -m ruff check pyproject.toml app tests` 在 2026-08-06 通过。
- `uv run python -m pytest` 最近一次全量通过，113 个测试全部通过。
- `.venv/bin/python -m pytest tests/test_streaming_generation.py` 在 2026-08-06 通过，覆盖流式读取超时配置和普通生成入队保存路径。
- `.venv/bin/python -m pytest tests/test_streaming_generation.py tests/test_orchestration_phase_3_4.py tests/test_generation_queue.py` 在 2026-08-06 通过，30 个测试全部通过，覆盖流式断流 salvage/重试、ChangeSet apply 跨 run 资产复用和 LLM 请求错误重新排队。
- `uv run ruff check app alembic tests` 通过，覆盖 Phase 1-2 新增文件。
- `uv run python -m compileall app` 通过。
- `uv run python -m pytest tests/test_design_assets_phase_1_2.py` 通过，3 个测试全部通过。
- `uv run python -m pytest tests/test_orchestration_phase_3_4.py tests/test_design_assets_phase_1_2.py` 通过，8 个测试全部通过。
- `uv run python -m pytest tests/test_orchestration_phase_3_4.py tests/test_design_assets_phase_1_2.py tests/test_prompt_template_contracts.py` 在 2026-08-06 通过，22 个测试全部通过，覆盖新版 UI 输出契约和编排上下文。
- `uv run python -m pytest tests/test_orchestration_phase_3_4.py tests/test_design_assets_phase_1_2.py tests/test_prompt_template_contracts.py` 在 2026-08-07 通过，23 个测试全部通过，覆盖新版前端工程实现输出契约和编排上下文。
- `uv run python -m pytest tests/test_structured_drafts.py tests/test_orchestration_phase_3_4.py tests/test_prompt_template_contracts.py` 在 2026-08-07 通过，29 个测试全部通过，覆盖新版 API 契约输出 schema、结构化草案、编排 fixture 和 prompt 模板契约。
- `uv run python -m pytest tests/test_prompt_template_contracts.py tests/test_orchestration_phase_3_4.py tests/test_design_assets_phase_1_2.py` 在 2026-08-07 通过，26 个测试全部通过，覆盖新版后端工程实现输出 schema、模板注册、ChangeSet apply 资产保存和历史资产接口兼容。
- `uv run python -m pytest tests/test_structured_drafts.py tests/test_generation_queue.py tests/test_orchestration_phase_3_4.py tests/test_prompt_template_contracts.py` 在 2026-08-07 通过，47 个测试全部通过，覆盖新版数据库模型输出 schema、旧 `entities` 兼容映射、队列和编排路径。
- `uv run python -m pytest tests/test_projects.py tests/test_business_requirement_stories.py tests/test_structured_drafts.py tests/test_generation_queue.py` 通过，66 个测试全部通过。
- `uv run python -m pytest tests/test_projects.py::test_delete_project_removes_all_related_content -q` 通过，验证旧 DB mock 已切换到新版 `database_tables` 输出结构。
- `uv run python -m pytest -q` 在 2026-08-08 通过，131 个测试全部通过，覆盖去蓝图化编排、一次性需求/变更集消耗、分层资产版本链和提示词输入契约。
- `uv run python -m ruff check app tests alembic --output-format=concise` 在 2026-08-08 通过。
- `DATABASE_URL=postgresql+psycopg://llh@localhost:5432/context_orchestrator_test uv run python -m alembic upgrade head` 通过，从空测试库升级到 `20260714_0011`。
- 当前环境中 `uv run <console-script>` 可能出现 spawn 失败，因此 Makefile 使用 `uv run python -m ...` 调用 alembic、uvicorn、ruff 和 pytest。
- 当前仓库 `.venv/bin/pytest` console script 的 shebang 仍指向旧目录，测试时可直接使用 `.venv/bin/python -m pytest`。
- `uv run python -m pytest tests/test_prompt_template_contracts.py tests/test_streaming_generation.py tests/test_generation_queue.py tests/test_orchestration_phase_3_4.py -q` 在 2026-08-07 通过，42 个测试全部通过，覆盖 Instructor typed generation、prompt 不注入 schema、队列和 Phase 3-4 编排主路径。
- `uv run python -m ruff check app tests --output-format=concise` 在 2026-08-07 通过。
- `uv run python -m pytest -q tests/test_prompt_template_contracts.py` 通过，覆盖 prompt 模板目录、同级 schema 文件、payload 不注入 schema 和 response model 注册。
- `uv run python -m pytest tests/test_prompt_template_contracts.py` 在 2026-08-07 通过，10 个测试全部通过；同日用 Jinja2 编译全部 `app/prompts/templates/*/prompt.j2` 并渲染 `api_contract_generator` 通过，确认该模板没有运行时 Jinja 语法错误。
- `uv run python -m pytest tests/test_prompt_template_contracts.py -q` 在 2026-08-07 通过，10 个测试全部通过且有 1 个上游 deprecation warning，覆盖新版 `Input Fields` / `Output Fields` / `Output Rules` USER 契约；`uv run python -m ruff check tests/test_prompt_template_contracts.py --output-format=concise` 和 `uv run python -m ruff check app tests --output-format=concise` 同日通过。
- `uv run python -m pytest -q tests/test_template_items.py` 通过，验证改动没有影响既有占位资源接口。
- `tests/test_blueprint_generation.py` 和 `tests/test_structured_drafts.py` 在 2026-08-05 手动补跑时命中现有 PostgreSQL 测试 fixture 的重复表/重复用户数据问题并被中断，未作为本次 prompt/schema 改动的有效回归结论。
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
- 后台队列测试覆盖 worker 未启动 503、入队、查询、取消 queued、领取最早任务、`FOR UPDATE SKIP LOCKED` 防重复领取、五类生成任务 worker 执行、LLM 请求失败重试、非重试失败、stale running 恢复、并发 worker pool 多槽位领取、stale recovery 并发安全、`QUEUE_WORKER_CONCURRENCY` 配置校验和 `/stream` 弃用。
- Blueprint 生成在项目已有业务需求故事时，会在 `content.business_requirement_stories` 中包含故事标题、优先级、状态和用户故事；无故事时保持原逻辑。
- Blueprint 生成器内部未知异常会记录 failed `GenerationRun`，并转换为中文可读 HTTP 500。
- 生成 API contract、DB model、Context Pack，支持列表、详情、role 过滤和 Markdown 导出；无 LLM 必填配置时走 deterministic fallback。
- Context Pack 可在缺少 API contract 或 DB model 时生成，并在 prompt 中标记缺失上下文。
- Consistency check 覆盖 warning 和 passed 状态。
- 删除 Project 后关联 Requirement、BusinessRequirementStory、GenerationRun 和第二批结构化草案 cascade 清理。
- 删除 Project 后项目详情和按项目访问 requirements、blueprints、api-contracts、db-models、context-packs 均返回 404，已删除关联资源详情不可再访问。
- 旧 auth/template_items 占位接口保持测试通过。
- Auth 测试覆盖邮箱登录 Cookie、用户名登录请求 422、错误邮箱或密码 401、邮箱大小写/空白归一化、禁用用户 403、登录 OpenAPI schema、`/auth/me` 安全响应、未登录业务接口 401、邮箱验证码发送兼容路径、邮箱验证码注册成功和弱密码拒绝；测试 fixture 默认创建真实用户并通过邮箱登录拿 Cookie。
- 多租户测试覆盖用户内项目访问、项目 owner 写入、独立资源 ID 访问权限和删除项目后关联资源不可访问。
- Phase 1-2 资产测试覆盖 Project configuration/config 读取/PATCH、新旧配置字段别名，UX/UI 与四类前后端设计资产列表/详情/版本化 PATCH、版本倒序、跨项目权限隔离，`FrontendImplementation`/`BackendImplementation` 新路由别名，ChangeSet 列表、旧 Blueprint/API Contract/DB Model/ContextPack 版本化 PATCH，以及 `prompt-packs` alias。
- Phase 3-4 编排测试覆盖 Story execute 入队并生成含 UX/UI layer 的 ChangeSet、ChangeSet apply 按 UX -> UI -> 前端页面结构顺序生成资产、页面结构输入读取 UX/UI、蓝图输出 UX/UI 摘要、PromptPack 包含 UX/UI 差异、applied 状态 apply 返回 409、regenerate 创建新 ChangeSet、显式 prompt-pack generate 只生成 ContextPack。

## Current Decisions and Conventions

- 新任务定义优先于旧 scaffold 定义；不保留旧环境变量兼容层。
- 新核心接口不使用旧 `ApiResponse` 包装。
- `ProjectBlueprint.content`、`GenerationRun` snapshots 和第二批 draft/context content 在应用和测试中都使用 PostgreSQL JSONB。
- `Project.name` 当前采用 `(owner_user_id, name)` 唯一约束，因此不同用户可以同名；同一用户内大小写敏感唯一，service layer 会先 trim 再查重，并捕获数据库 `IntegrityError` 转成业务 409。
- 用户角色固定为 `user`、`vip-plus`、`vip-pro`、`vip-pro-max`、`admin`；本批不做会员限流或功能差异化，所有非 admin 角色可使用同样普通功能。
- Admin 不可管理其他 admin，也不可把非 admin 用户提升为 admin；如未来需要超级管理员，需要新增独立权限模型。
- `GenerationRun` 是后台生成队列任务表，记录 `queued/running/completed/failed/cancelled` 状态；`generate_blueprint`、`generate_api_contract`、`generate_db_model`、`generate_context_packs`、`generate_business_requirement_stories`、`generate_change_set`、`apply_change_set`、`generate_prompt_pack` 都通过队列执行。
- `QUEUE_WORKER_ID` 是 worker 标识的可选覆盖项；未配置时 `run_worker_loop()` 自动生成 `hostname:pid:uuid8`。并发数为 `1` 时使用该 base id；并发数大于 `1` 时派生为 `base:1`、`base:2` 等，并在超过 `generation_workers.worker_id` 长度限制时截断并追加短 hash，避免多槽位复用同一心跳记录和 `locked_by` 标识。
- `GenerationRun` 成功状态统一写 `completed`；业务故事状态查询接口会把 `completed` 兼容映射为前端既有 `succeeded`。成功 `output_snapshot` 记录 `raw_text_length`、资源 id 或资源 id 列表、counts 和 summary；失败 `output_snapshot` 记录 `failure_stage` 和可选 `raw_text_length`，并保存 `error_message`。
- `LLM_STRUCTURED_MAX_RETRIES` 控制 Instructor schema 校验重试次数，默认 `2`；业务故事、蓝图、API Contract、DB Model、ChangeSet、设计资产、PromptPack 和 ContextPack 统一使用 `output_schema.py` 的 Pydantic `response_model` 约束结构化输出。
- 对于跨任务传递的字段，当前约定是“上一步输出的 JSON 片段 -> 下一步 service 重新封装”。例如业务故事输出的 `title/priority/implementation_scope/affected_layers/user_story/business_scope/data_rules/acceptance_criteria` 会落库成 `BusinessRequirementStory`；ChangeSet 的 `affected_layers`、`recommended_prompt_strategy`、`module_changes` 和 `diff` 会决定后续哪些层生成、是否生成 prompt pack；DesignAsset 编排会把 `latest_assets_snapshot`、`previous_version`、`related_assets`、`change_set` 和 `project_config` 拼进下一层 prompt；PromptPack 则消费 `old_versions/new_versions/project_blueprint/change_set/diff_summary` 生成执行指令。
- 业务需求故事优先级固定为 `p1_must`、`p2_should`、`p3_could`、`p4_wont`；新工作流状态为 `draft`、`ready`、`selected`、`applied`、`implemented`、`verified`、`deferred`，schema 暂时兼容旧 `in_progress`、`done`；生成默认 `draft`，`POST /business-stories/{story_id}/select` 会把状态更新为 `selected`。
- 业务需求故事新增 `implementation_scope`、`affected_layers`、`depends_on`、`source_requirement_ids`、`execution_notes`，用于后续 ChangeSet 编排；业务故事和 ChangeSet prompt 均要求区分 UX/UI 影响层：用户路径、交互流程、状态反馈、空状态、错误状态和权限体验归入 `ux_design`，视觉层级、布局、颜色语义、组件样式、按钮层级、Badge 和响应式规则归入 `ui_design`；旧输出缺失字段仍使用数据库默认值。
- ChangeSet apply 只允许 `draft`、`ready`、`failed` 状态入队；`applied` 或 `discarded` 返回 409 且不创建 run。成功 apply 后会把 ChangeSet 标记为 `applied`。
- ChangeSet apply 采用“按 affected layer 逐资产调用 LLM、全部校验通过后统一提交”的模式；若任一 LLM 输出解析、校验或保存失败，worker 会 rollback 并把 run 标记 failed，避免半套资产落库。
- ChangeSet apply 的前端页面结构生成必须读取最新或本轮刚生成的 `ux_design` 与 `ui_design`，页面结构只负责页面、组件、路由、目录、文件路径、数据依赖和 API client 落点，通过 `ux_refs`、`ui_refs` 引用 UX/UI。
- ProjectBlueprint 汇总 prompt 会读取最新 UX/UI、前端、后端、API、DB 设计资产，并在 content 中保留 `ux_summary` 和 `ui_summary`。
- PromptPack 当前保存为 `ContextPack(role="prompt_pack")`，并在模型/schema 层导出为 `PromptPack` 语义别名；content 使用新版 prompt pack JSON 结构，`prompt_text` 由 UX/UI 差异、frontend prompt 和 backend prompt 合并为 Markdown。
- 业务需求故事 LLM 输出必须是 JSON object，顶层含非空 `stories` list；每个故事必须含 `title`、`priority`、`user_story`、`business_scope`、`data_rules`、`acceptance_criteria`，其中 `business_scope` 会规范化为 `included` 和 `excluded`。若未生成任何有效故事，生成任务失败并记录“未生成有效业务需求故事。”。
- 业务需求故事 PATCH 使用 `model_dump(exclude_unset=True)` 做局部更新；`user_story` 保存 trim 后非空字符串；`business_scope` 保存为 `{"included": list[str], "excluded": list[str]}`，缺失项补空数组；`data_rules` 允许 `{rule}` 或 `{field, rule}`，过滤空 rule；`acceptance_criteria` trim 并过滤空字符串。
- 业务需求故事生成仍在兼容 fallback stream 路径向 LLM 请求传入 `response_format={"type":"json_object"}`；真实配置完整时默认走 Instructor typed generation。解析或结构校验失败直接返回 502 并记录 failed `GenerationRun`。
- 旧同步 `BusinessStoryGenerationService` 已移除手写二次 repair prompt，改用统一 Instructor typed response model 和 `json-repair` JSON 语法修复兜底；schema 或业务结构校验失败仍按现有错误映射失败。
- 当前项目已引入 `Instructor`、`openai` 和 `json-repair`，并在真实 LLM 调用路径使用 typed response model；`app/prompts/templates/*/output_schema.py` 和 `app/prompts/template_registry.py` 是 runtime contract 来源，prompt 本身不再注入 schema。
- Blueprint、API contract、DB model 和 ContextPack/PromptPack 每次生成创建新记录，version 从 1 开始递增；手动 PATCH 也创建新版本记录并保留旧版本。当前去蓝图化主链路下，ProjectBlueprint 仅用于历史兼容，不再驱动默认生成。
- `Project` ORM 技术栈字段为 `target_frontend_stack` 和 `target_backend_stack`；读取 ORM 对象时不要使用旧字段名 `frontend_stack` 或 `backend_stack`。默认值只能从 `app/core/constants.py` 引用，避免在 model、schema、service、prompt 或 generator 中重复硬编码。
- Context Pack 第一批固定生成 `frontend_engineer` 和 `backend_engineer` 两种角色。
- Markdown export 返回 JSON：`filename`、`content_type`、`content`，不返回文件流。
- LLM 输出必须是 JSON object；`app/llm/json_client.py` 会兼容去除外层 Markdown code fence 后解析 JSON，并在严格解析失败时尝试 `json-repair` 语法修复。
- `POST /api/v1/projects/{project_id}/generate/blueprint`、`/api-contract`、`/db-model` 默认不再静默 fallback 到 deterministic 数据；生成接口成功入队返回 202，LLM 配置、请求、空输出、格式、校验和保存失败由 worker 写入 failed `GenerationRun`。业务故事更新、ChangeSet 生成、设计资产应用和 PromptPack 生成构成主编排路径，蓝图只作为旧数据兼容层保留。
- 普通生成接口的业务前置错误（如项目、需求、蓝图缺失）仍使用普通 HTTP 4xx 且不创建 `GenerationRun`；入队后错误不再通过原 POST 响应返回，而是通过 `GET /api/v1/generation-runs/{run_id}` 查询状态和错误。
- LLM 请求不传入 `max_tokens` 或 `temperature`，项目侧不设置输出 token 上限和生成温度，相关行为交由模型服务默认策略处理。
- 当前 README、`.env.example` 和 `.env` 使用 DashScope OpenAI-compatible 示例：`https://dashscope.aliyuncs.com/compatible-mode/v1` + `qwen-plus`。
- Prompt 输出契约的可查看来源是 `app/prompts/templates/<template>/output_schema.py`；对应 `prompt.j2` 在同一目录，Jinja 变量名保持英文。不要再引入手写 `output_structure.json` 作为第二来源。
- UI 视觉设计新版公开内容契约为 `visual_system/layout_rules/component_style_rules`；旧 `visual_hierarchy/layout_guidelines/badge_rules/button_rules/form_rules/responsive_rules/accessibility_visual_rules` 仅作为历史内容兼容，不应出现在新生成输出中。
- 前端工程实现新版公开内容契约为 `route_definitions/directory_structure/code_logic/environment_variables/design_theme/dependencies`；旧 `pages/components/data_flow/internal_utilities/install_commands` 仅作为历史内容兼容，不应出现在新生成输出中。
- 后端工程实现新版公开内容契约为 `directory_structure/code_logic/utility_classes/llm_interaction_templates/environment_variables/dependencies`；旧 `services/cross_cutting_rules/api_mappings/database_mappings/external_services/internal_utilities/install_commands` 仅作为历史内容兼容，不应出现在新生成输出中。
- API 契约新版公开内容契约为 `api_base_path/api_resource_groups/endpoints/request_schema/response_schema/error_model`；旧 `base_path/resources/schemas/status_codes/request_body/response_body` 仅作为历史内容兼容，不应出现在新生成输出中。
- 数据库模型新版公开内容契约为 `database_tables/fields`；旧 `entities` 仅作为历史内容兼容，不应出现在新生成输出中。
- LLM `prompt.j2` 是运行时真实来源，不只是说明文档；静态角色、任务说明、输入解释、输出解释、规则、禁止事项和典型示例都应放在模板内。
- 每个 LLM 模板必须且只能包含一个 `===SYSTEM===` 和一个 `===USER===`，`===USER===` 内固定包含同级小节 `Input:`、`Input Fields:`、`Output Fields:`、`Output Rules:`，其子项统一使用 `  - ` 缩进，并使用成对的 `Example Input [n]` / `Example Output [n]`。
- `Output Fields:` 必须描述输出字段取值说明，包括关键顶层和嵌套字段的类型、枚举值、布尔含义、数组/object 结构、可空值/default 含义和业务语义；`Output Rules:` 承载 JSON-only、禁止 Markdown、跨层一致性、diff/reference 规则、禁止生成代码等格式和业务纪律。
- Python prompt builder 只负责构造动态变量上下文，不再向 prompt 注入 `model_json_schema()`；运行时通过 `build_*_prompt()` 渲染模板后，把 typed `response_model` 交给 LLM runtime。
- `app/prompts/renderer.py` 使用 Jinja2 `StrictUndefined` 渲染模板，缺变量、marker 缺失、marker 重复或 system/user 为空都应失败。
- LLM 输出结构采用双层检查：LLM runtime 的 Pydantic `response_model` 先约束输出形状，service validator 负责业务归一化、兜底和错误映射。
- 模板契约测试必须覆盖模板文件存在、固定章节、Example 成对、可渲染、system/user 非空、schema model 对齐和 renderer 错误路径。

## Known Issues and Follow-ups

- 尚未实现超级管理员、审计日志、登录失败限流、密码重置、多用户协作、生产监控和会员功能限流。
- `AUTH_SECRET_KEY` 生产环境必须配置强随机值；默认开发 fallback 仅用于本地调试，不应上线使用。
- SMTP 未配置时验证码只写后端日志用于开发；QQ 邮箱配置使用 `SMTP_HOST=smtp.qq.com`、`SMTP_PORT=465`、`SMTP_CODE` 授权码和 `SMTP_SENDER_EMAIL` 发件邮箱，465 端口自动使用 `SMTP_SSL`；生产环境需要配置 SMTP 并避免日志采集暴露验证码。
- 后台队列当前只自动恢复 stale `running` 任务；对长期 `queued` 等待任务尚无超时失败、告警、管理端重排或强制失败机制。
- Phase 3-4 真实 LLM 环境尚需人工端到端验收；当前自动化测试通过 monkeypatch LLM stream 验证结构化链路。
- ChangeSet apply 当前没有项目级互斥锁；同一项目多个 apply 并发时可能生成相邻版本竞态，生产化可增加 project-level advisory lock 或队列领取条件。
- 多 worker 并发池当前不做 project/module 级互斥；如果未来发现同一项目多种生成任务同时写入最新资源导致业务竞态，可增加 project/module 级领取条件、advisory lock 或幂等约束。
- `running` 生成任务尚不支持提前终止；如需支持，需要增加协作式取消状态并在 worker 的 LLM 调用前后、解析前、保存前检查取消请求。
- Consistency check 当前只做基础结构一致性检查，后续可扩展为 schema/endpoint/DB 字段级别校验。
- Context Pack prompt 在真实运行时由 LLM 生成；测试 fallback 仍使用本地模板文案，后续可扩展为可配置模板和版本管理。
- Blueprint、API Contract、DB Model 已默认接入 LLM，测试通过 monkeypatch/mock `generate_json` 返回结构化 payload；真实模型环境仍需人工端到端验收。
- TestClient 当前有 StarletteDeprecationWarning，提示未来可能需要使用 `httpx2`。
- 如果已有数据库中存在完全相同的 `projects.name`，迁移 `20260709_0004` 会失败；上线前需要先清理历史重复数据。若未来要求大小写不敏感唯一，可改为 PostgreSQL functional unique index，如 `lower(name)`。
