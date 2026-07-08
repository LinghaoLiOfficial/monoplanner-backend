.PHONY: install migrate run dev lint test

UVICORN_RELOAD_ARGS = --reload --reload-dir app --reload-include '*.py' --reload-include '.env' --reload-exclude '.venv/*' --reload-exclude '*.pyc'

install:
	uv sync

migrate:
	uv run python -m alembic upgrade head

run:
	uv run python -m uvicorn app.main:app $(UVICORN_RELOAD_ARGS)

dev:
	uv run python -m alembic upgrade head
	uv run python -m uvicorn app.main:app $(UVICORN_RELOAD_ARGS)

lint:
	uv run python -m ruff check .

test:
	uv run python -m pytest
