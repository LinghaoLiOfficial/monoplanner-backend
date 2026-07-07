from collections.abc import Generator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionLocal


async def get_db() -> Generator[AsyncSession, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        await db.close()
