from collections.abc import Generator
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.session import get_db_session
from app.models.user import User


def get_db() -> Generator[Session, None, None]:
    yield from get_db_session()


DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbSession,
    access_token: Annotated[str | None, Cookie(alias=settings.auth_cookie_name)] = None,
) -> User:
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录。")
    try:
        user_id = decode_access_token(access_token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录状态无效或已过期。",
        ) from exc
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在。")
    return user


def get_active_user(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="用户已被禁用。")
    return current_user


def require_admin(current_user: Annotated[User, Depends(get_active_user)]) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限。")
    return current_user
