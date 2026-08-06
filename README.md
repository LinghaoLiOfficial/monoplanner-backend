# Fullstack Context Orchestrator API

FastAPI 后端基础骨架，用于把自然语言业务需求编排为结构化 Project Blueprint、API 契约草案、数据库模型草案和 Codex Context Pack。生成链路已接入 OpenAI-compatible 真实 LLM API；未配置 LLM 必填参数时会使用 deterministic fallback。

## 技术栈

- Python 3.12+
- FastAPI
- Uvicorn
- SQLAlchemy 2.x
- Alembic
- PostgreSQL
- uv

## `.env` 配置

项目只使用根目录单个 `.env`，可从 `.env.example` 复制：

```bash
cp .env.example .env
```

`.env.example` 模板：

```env
APP_NAME=Fullstack Context Orchestrator API
BACKEND_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
DATABASE_URL=postgresql+psycopg://llh@localhost:5432/context_orchestrator
TEST_DATABASE_URL=postgresql+psycopg://llh@localhost:5432/context_orchestrator_test

# LLM API (OpenAI-compatible). Uncomment and fill these values to enable real LLM generation.
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=replace-with-your-api-key
LLM_MODEL=qwen-plus
LLM_TIMEOUT_SECONDS=60
LLM_STREAM_READ_TIMEOUT_SECONDS=300
LLM_THINKING=false

# Background generation queue
QUEUE_WORKER_CONCURRENCY=1
QUEUE_POLL_INTERVAL_SECONDS=2
QUEUE_STALE_AFTER_SECONDS=900
QUEUE_WORKER_HEARTBEAT_TIMEOUT_SECONDS=15
QUEUE_MAX_ATTEMPTS=3
```

LLM 配置说明：

- `LLM_BASE_URL`: OpenAI-compatible API base URL，不需要包含 `/chat/completions`，例如阿里云 DashScope 兼容模式 `https://dashscope.aliyuncs.com/compatible-mode/v1`。
- `LLM_API_KEY`: 模型服务 API Key，请只放在本机 `.env` 或部署环境变量中，不要提交真实密钥。
- `LLM_MODEL`: 文本模型名，例如 `qwen-plus`。
- `LLM_TIMEOUT_SECONDS`: 单次请求超时时间，单位秒，默认 `60`。
- `LLM_STREAM_READ_TIMEOUT_SECONDS`: 流式响应连续无数据读取超时时间，单位秒，默认 `300`；应用变更集等长生成建议保持高于 `LLM_TIMEOUT_SECONDS`。
- `LLM_THINKING`: 是否启用支持思考模式的模型参数，默认 `false`。

队列配置说明：

- `QUEUE_WORKER_CONCURRENCY`: 单个 worker 进程内的并发线程数，默认 `1`。大于 `1` 时每个执行槽位使用独立数据库 session 和派生 worker id，并通过 PostgreSQL 行锁领取不同任务。
- `QUEUE_POLL_INTERVAL_SECONDS`: worker 空闲轮询间隔，默认 `2`。
- `QUEUE_STALE_AFTER_SECONDS`: running 任务超时恢复阈值，默认 `900`。
- `QUEUE_WORKER_HEARTBEAT_TIMEOUT_SECONDS`: worker 心跳有效期，生成接口在有效期内找不到在线 worker 时返回 503，默认 `15`。
- `QUEUE_MAX_ATTEMPTS`: 可重试任务最大尝试次数，默认 `3`。
- `QUEUE_WORKER_ID`: 高级可选覆盖项，普通开发和单实例部署不需要设置；未配置时 worker 会自动生成唯一标识。多 worker 部署时不要让多个 worker 复用同一个固定值。

## 启动数据库

```bash
brew services start postgresql@14
createdb context_orchestrator
createdb context_orchestrator_test
```

开发和生产默认连接宿主机本地 PostgreSQL：`DATABASE_URL=postgresql+psycopg://llh@localhost:5432/context_orchestrator`。自动化测试使用独立测试库：`TEST_DATABASE_URL=postgresql+psycopg://llh@localhost:5432/context_orchestrator_test`，测试库名必须以 `_test` 结尾。

## 安装依赖

```bash
uv sync
```

若需要运行测试和 lint：

```bash
uv sync --group dev
```

## 运行 Migration

```bash
uv run python -m alembic upgrade head
```

当前迁移会创建：

- `template_items`
- `projects`
- `requirements`
- `project_blueprints`
- `generation_runs`
- `business_requirement_stories`
- `api_contract_drafts`
- `db_model_drafts`
- `context_packs`

## 启动后端

```bash
uv run python -m uvicorn app.main:app --reload
```

服务默认地址为 [http://127.0.0.1:8000](http://127.0.0.1:8000)，OpenAPI 文档为 [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)。

LLM 生成接口使用 PostgreSQL-backed 后台队列。另开一个终端启动 worker：

```bash
uv run python -m app.workers.generation_worker
```

也可以使用 Makefile：

```bash
make workers
make dev-all
```

其中 `make workers` 只启动后台队列 worker 并发池，并按 `QUEUE_WORKER_CONCURRENCY` 启动执行槽位；`make dev-all` 会先执行 migration，然后同时启动 worker 和 FastAPI 开发服务。

生成接口会先检查最近 worker 心跳；如果 worker 未启动或心跳过期，直接返回 503，不创建 queued 任务。

生成接口返回 `202 Accepted` 和 `GenerationRun` 状态对象，前端可轮询 `GET /api/v1/generation-runs/{run_id}`；任务完成后再通过对应资源列表或详情接口读取保存结果。旧 `/generate/{module}/stream` 接口已弃用并返回 410。

## Docker 启动

`docker compose up api worker` 会让 API 和 worker 容器通过 `host.docker.internal:5432` 连接宿主机 PostgreSQL。请先确保宿主机 PostgreSQL 已启动、`context_orchestrator` 数据库已存在，并允许来自 Docker Desktop 的本地连接。API 容器负责执行 migration，worker 容器只运行后台队列 worker，并按 `QUEUE_WORKER_CONCURRENCY` 启动并发执行池。

仓库保留了一个可选的 Compose PostgreSQL 服务，仅用于临时本地辅助数据库：

```bash
docker compose --profile local-db up -d db
```

## 核心 API

统一前缀：`/api/v1`

- `GET /api/v1/health`
- `POST /api/v1/projects`
- `GET /api/v1/projects`
- `GET /api/v1/projects/{project_id}`
- `PATCH /api/v1/projects/{project_id}`
- `GET /api/v1/projects/{project_id}/configuration`
- `PATCH /api/v1/projects/{project_id}/configuration`
- `GET /api/v1/projects/{project_id}/config`（兼容别名）
- `PATCH /api/v1/projects/{project_id}/config`（兼容别名）
- `DELETE /api/v1/projects/{project_id}`
- `POST /api/v1/projects/{project_id}/requirements`
- `GET /api/v1/projects/{project_id}/requirements`
- `GET /api/v1/projects/{project_id}/blueprints`
- `GET /api/v1/blueprints/{blueprint_id}`
- `POST /api/v1/projects/{project_id}/generate/blueprint`
- `POST /api/v1/projects/{project_id}/generate/business-stories`
- `GET /api/v1/projects/{project_id}/business-stories`
- `GET /api/v1/business-stories/{story_id}`
- `PATCH /api/v1/business-stories/{story_id}`
- `DELETE /api/v1/business-stories/{story_id}`
- `GET /api/v1/projects/{project_id}/ux-designs`
- `GET /api/v1/projects/{project_id}/ui-designs`
- `GET /api/v1/projects/{project_id}/frontend-implementations`
- `GET /api/v1/frontend-implementations/{asset_id}`
- `PATCH /api/v1/frontend-implementations/{asset_id}`
- `GET /api/v1/projects/{project_id}/backend-implementations`
- `GET /api/v1/backend-implementations/{asset_id}`
- `PATCH /api/v1/backend-implementations/{asset_id}`
- `POST /api/v1/projects/{project_id}/generate/api-contract`
- `GET /api/v1/projects/{project_id}/api-contracts`
- `GET /api/v1/api-contracts/{api_contract_id}`
- `POST /api/v1/projects/{project_id}/generate/db-model`
- `GET /api/v1/projects/{project_id}/db-models`
- `GET /api/v1/db-models/{db_model_id}`
- `POST /api/v1/projects/{project_id}/generate/context-packs`
- `GET /api/v1/generation-runs/{run_id}`
- `POST /api/v1/generation-runs/{run_id}/cancel`
- `GET /api/v1/projects/{project_id}/context-packs`
- `GET /api/v1/context-packs/{context_pack_id}`
- `POST /api/v1/context-packs/{context_pack_id}/export`
- `GET /api/v1/projects/{project_id}/prompt-packs`
- `GET /api/v1/prompt-packs/{context_pack_id}`
- `POST /api/v1/projects/{project_id}/prompt-packs/generate`
- `GET /api/v1/projects/{project_id}/consistency-check`

## 手动验证

```bash
curl http://127.0.0.1:8000/api/v1/health

PROJECT_ID=$(curl -s -X POST http://127.0.0.1:8000/api/v1/projects \
  -H 'Content-Type: application/json' \
  -d '{"name":"Demo Project","description":"Context orchestrator demo"}' | jq -r .id)

curl -X POST "http://127.0.0.1:8000/api/v1/projects/$PROJECT_ID/requirements" \
  -H 'Content-Type: application/json' \
  -d '{"raw_text":"做一个可以把业务需求转成结构化上下文包的工具"}'

curl -X POST "http://127.0.0.1:8000/api/v1/projects/$PROJECT_ID/generate/business-stories" \
  -H 'Content-Type: application/json' \
  -d '{"requirement_id":null,"overwrite":false}'
RUN_ID=$(curl -s -X POST "http://127.0.0.1:8000/api/v1/projects/$PROJECT_ID/generate/blueprint" | jq -r .id)
curl "http://127.0.0.1:8000/api/v1/generation-runs/$RUN_ID"
curl "http://127.0.0.1:8000/api/v1/projects/$PROJECT_ID/business-stories"
curl -X POST "http://127.0.0.1:8000/api/v1/projects/$PROJECT_ID/generate/api-contract"
curl -X POST "http://127.0.0.1:8000/api/v1/projects/$PROJECT_ID/generate/db-model"
curl -X POST "http://127.0.0.1:8000/api/v1/projects/$PROJECT_ID/generate/context-packs"
curl "http://127.0.0.1:8000/api/v1/projects/$PROJECT_ID/blueprints"
curl "http://127.0.0.1:8000/api/v1/projects/$PROJECT_ID/api-contracts"
curl "http://127.0.0.1:8000/api/v1/projects/$PROJECT_ID/db-models"
curl "http://127.0.0.1:8000/api/v1/projects/$PROJECT_ID/context-packs"
curl "http://127.0.0.1:8000/api/v1/projects/$PROJECT_ID/consistency-check"
```


## 测试和检查

```bash
uv run python -m ruff check .
uv run python -m pytest
```

## 当前未实现

- 登录注册和复杂用户权限
- 前端代码
- 多用户协作
- 生产级监控、审计和限流

## 常用命令

```bash
make install
make migrate
make run
make dev
make lint
make test
```
