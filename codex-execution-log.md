
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
