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

# LLM API (OpenAI-compatible). Uncomment and fill these values to enable real LLM generation.
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=replace-with-your-api-key
LLM_MODEL=qwen-plus
LLM_TIMEOUT=60
LLM_TIMEOUT_SECONDS=60
LLM_THINKING=false
```

LLM 配置说明：

- `LLM_BASE_URL`: OpenAI-compatible API base URL，不需要包含 `/chat/completions`，例如阿里云 DashScope 兼容模式 `https://dashscope.aliyuncs.com/compatible-mode/v1`。
- `LLM_API_KEY`: 模型服务 API Key，请只放在本机 `.env` 或部署环境变量中，不要提交真实密钥。
- `LLM_MODEL`: 文本模型名，例如 `qwen-plus`。
- `LLM_TIMEOUT`: 单次请求超时时间，单位秒，默认 `60`。
- `LLM_TIMEOUT_SECONDS`: OpenAI-compatible 业务需求故事生成接口的请求超时时间，单位秒，默认 `60`。
- `LLM_THINKING`: 是否启用支持思考模式的模型参数，默认 `false`。

## 启动数据库

```bash
```

使用本机 PostgreSQL（Homebrew `postgresql@14`）并保证 `DATABASE_URL` 可连接。

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

## 核心 API

统一前缀：`/api/v1`

- `GET /api/v1/health`
- `POST /api/v1/projects`
- `GET /api/v1/projects`
- `GET /api/v1/projects/{project_id}`
- `PATCH /api/v1/projects/{project_id}`
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
- `POST /api/v1/projects/{project_id}/generate/api-contract`
- `GET /api/v1/projects/{project_id}/api-contracts`
- `GET /api/v1/api-contracts/{api_contract_id}`
- `POST /api/v1/projects/{project_id}/generate/db-model`
- `GET /api/v1/projects/{project_id}/db-models`
- `GET /api/v1/db-models/{db_model_id}`
- `POST /api/v1/projects/{project_id}/generate/context-packs`
- `GET /api/v1/projects/{project_id}/context-packs`
- `GET /api/v1/context-packs/{context_pack_id}`
- `POST /api/v1/context-packs/{context_pack_id}/export`
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
curl "http://127.0.0.1:8000/api/v1/projects/$PROJECT_ID/business-stories"
curl -X POST "http://127.0.0.1:8000/api/v1/projects/$PROJECT_ID/generate/blueprint"
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
