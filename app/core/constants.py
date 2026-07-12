DEFAULT_FRONTEND_STACK = "Next.js + React + TypeScript + Tailwind CSS 4 + Shadcn/ui + pnpm"
DEFAULT_BACKEND_STACK = (
    "Python 3.12 + FastAPI + Uvicorn + SQLAlchemy 2.x + Alembic + PostgreSQL + uv"
)


def normalize_stack(value: str | None, default: str) -> str:
    if value is None:
        return default
    normalized = value.strip()
    return normalized or default
