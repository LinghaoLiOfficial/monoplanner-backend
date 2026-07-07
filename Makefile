.PHONY: install migrate run dev lint test

UVICORN_RELOAD_ARGS = --reload --reload-dir app --reload-include '*.py' --reload-include '.env' --reload-exclude '.venv/*' --reload-exclude '*.pyc'

install:
	uv sync

migrate:
	uv run alembic upgrade head

run:
	uv run uvicorn app.main:app $(UVICORN_RELOAD_ARGS)

dev:
	uv run alembic upgrade head
	uv run uvicorn app.main:app $(UVICORN_RELOAD_ARGS)

lint:
	uv run ruff check .

test:
	uv run pytest
