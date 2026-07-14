.PHONY: install migrate run workers dev dev-all lint test

UVICORN_RELOAD_ARGS = --reload --reload-dir app --reload-include '*.py' --reload-include '.env' --reload-exclude '.venv/*' --reload-exclude '*.pyc'

install:
	uv sync

migrate:
	uv run python -m alembic upgrade head

run:
	uv run python -m uvicorn app.main:app $(UVICORN_RELOAD_ARGS)

workers:
	uv run python -m app.workers.generation_worker

dev:
	uv run python -m alembic upgrade head
	uv run python -m uvicorn app.main:app $(UVICORN_RELOAD_ARGS)

dev-all:
	uv run python -m alembic upgrade head
	(uv run python -m app.workers.generation_worker & \
	WORKER_PID=$$!; \
	trap 'kill $$WORKER_PID' INT TERM EXIT; \
	uv run python -m uvicorn app.main:app $(UVICORN_RELOAD_ARGS))

lint:
	uv run python -m ruff check .

test:
	uv run python -m pytest
