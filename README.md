# Fullstack Context Orchestrator API

FastAPI 后端基础骨架，用于把自然语言业务需求编排为结构化 Project Blueprint。当前批次只实现数据库、API、schema、service 和 deterministic mock blueprint generator，不接入任何真实 LLM。

## 技术栈

- Python 3.12+
- FastAPI
- Uvicorn
- SQLAlchemy 2.x
- Alembic
- PostgreSQL
- uv

## `.env` 配置

复制示例文件：

```bash
cp .env.dev.example .env
```

开发默认配置：

```env
APP_NAME=Fullstack Context Orchestrator API
APP_ENV=development
BACKEND_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
DATABASE_URL=postgresql+psycopg://llh@localhost:5432/context_orchestrator
```

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

## 手动验证

```bash
curl http://127.0.0.1:8000/api/v1/health

PROJECT_ID=$(curl -s -X POST http://127.0.0.1:8000/api/v1/projects \
  -H 'Content-Type: application/json' \
  -d '{"name":"Demo Project","description":"Context orchestrator demo"}' | jq -r .id)

curl -X POST "http://127.0.0.1:8000/api/v1/projects/$PROJECT_ID/requirements" \
  -H 'Content-Type: application/json' \
  -d '{"raw_text":"做一个可以把业务需求转成结构化上下文包的工具"}'

curl -X POST "http://127.0.0.1:8000/api/v1/projects/$PROJECT_ID/generate/blueprint"
curl "http://127.0.0.1:8000/api/v1/projects/$PROJECT_ID/blueprints"
```


## 测试和检查

```bash
uv run python -m ruff check .
uv run python -m pytest
```

## 当前未实现

- 真实 OpenAI、Claude、LangChain、LlamaIndex 或其他 AI 服务接入
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
