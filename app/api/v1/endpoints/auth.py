from fastapi import APIRouter, status

from app.core.exceptions import AppError, ErrorCode
from app.schemas.auth import LoginRequest

router = APIRouter(prefix="/auth")


@router.post("/login", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def login(_: LoginRequest) -> None:
    raise AppError(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        code=ErrorCode.AUTH_NOT_IMPLEMENTED,
        message="Authentication module is a scaffold placeholder. Implement your auth flow here.",
    )
