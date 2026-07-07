from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.common import ApiResponse, MessageResponse

router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/health")
async def health_check(db: DbSession) -> ApiResponse[MessageResponse]:
    await db.execute(text("SELECT 1"))
    return ApiResponse(data=MessageResponse(message="ok"))
