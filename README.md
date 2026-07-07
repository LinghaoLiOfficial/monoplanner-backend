# fullstack-forge-backend

`fullstack-forge-backend` 项目，技术栈为 `Python 3.12+ + FastAPI + Uvicorn + SQLAlchemy 2.x + Alembic + PostgreSQL`，包管理使用 `uv`。

## 推荐启动命令

完成 `.env` 配置后，优先使用：

```bash
make dev
```

这个命令会先执行数据库迁移，再启动开发服务，并限制热重载监听范围，减少控制台噪音。

## 技术栈

- Python 3.12+
- FastAPI
- Uvicorn
- SQLAlchemy 2.x
- Alembic
- PostgreSQL
- uv

说明：
当前项目实现使用了 SQLAlchemy 2.x 异步会话与 `asyncpg` 驱动；Alembic 迁移会自动切换为同步驱动执行。

## 快速开始

1. 安装依赖

```bash
uv sync
```

2. 复制环境变量模板

```bash
cp .env.dev.example .env
```

3. 准备数据库

确保 `.env` 中的 `DATABASE_URL` 可连接到可用 PostgreSQL 数据库。

默认开发连接串为：

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/fullstack_forge
```

4. 一键启动

```bash
make dev
```

5. 或手动执行

```bash
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --reload-dir app
```

服务默认地址为 [http://127.0.0.1:8000](http://127.0.0.1:8000)，OpenAPI 文档为 [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)。

## API 版本约定

- 当前统一前缀为 `/api/v1`
- 新增接口默认放入 `app/api/v1/endpoints/`
- 后续破坏性变更建议通过 `/api/v2` 另开版本，而不是直接覆盖 `v1`

## 统一响应约定

成功响应：

```json
{
  "status": "success",
  "data": {},
  "message": null
}
```

错误响应：

```json
{
  "status": "error",
  "code": "ERROR_CODE",
  "message": "Human readable message"
}
```

## 基础错误码约定

- `INTERNAL_ERROR`
- `VALIDATION_ERROR`
- `RESOURCE_NOT_FOUND`
- `CONFLICT`
- `AUTH_NOT_IMPLEMENTED`
- `UNAUTHORIZED`

## 分页约定

列表接口使用：

- `page`
- `page_size`

分页响应结构：

```json
{
  "status": "success",
  "data": {
    "items": [],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 0,
      "total_pages": 0
    }
  },
  "message": null
}
```

## 当前接口

- `GET /`
- `GET /api/v1/health`
- `GET /api/v1/template-items/`
- `POST /api/v1/template-items/`
- `POST /api/v1/auth/login`

## Docker 启动

```bash
docker compose up --build
```

启动后会自动等待 PostgreSQL 就绪并执行 `alembic upgrade head`。

## 常用命令

```bash
make install
make migrate
make run
make dev
make lint
make test
docker compose up --build
```

## 项目结构

```text
.
├── alembic/
├── app/
│   ├── api/
│   ├── core/
│   ├── crud/
│   ├── db/
│   ├── models/
│   ├── schemas/
│   ├── services/
│   └── main.py
├── tests/
├── .env.dev.example
├── .env.test.example
├── .env.prod.example
├── alembic.ini
├── pyproject.toml
└── Makefile
```

## 已包含内容

- FastAPI + Uvicorn 基础服务
- SQLAlchemy 2.x 数据访问层
- Alembic 数据库迁移
- PostgreSQL 连接配置
- `uv` 依赖与环境管理
- 统一异常处理
- 统一响应包装
- 分页协议
- 认证模块占位
- 多环境 `.env` 模板
- Docker / docker-compose
- GitHub Actions CI
- 独立测试数据库
