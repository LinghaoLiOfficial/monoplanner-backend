import logging
import smtplib
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from uuid import UUID

from fastapi import HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    generate_verification_code,
    hash_password,
    hash_verification_code,
    make_avatar_color,
    make_avatar_seed,
    validate_password_strength,
    verify_password,
    verify_verification_code,
)
from app.models.email_verification_code import EmailVerificationCode
from app.models.user import User
from app.schemas.auth import (
    AdminUserUpdateRequest,
    RegisterRequest,
    SendEmailVerificationResponse,
    UpdateMeRequest,
)

logger = logging.getLogger(__name__)
REGISTER_PURPOSE = "register"
MAX_VERIFICATION_ATTEMPTS = 5
MANAGEABLE_ROLES = {"user", "vip-plus", "vip-pro", "vip-pro-max"}
ALL_ROLES = MANAGEABLE_ROLES | {"admin"}


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def send_register_code(self, email: str) -> SendEmailVerificationResponse:
        normalized_email = _normalize_email(email)
        self._ensure_email_available(normalized_email)
        self._ensure_can_resend(normalized_email)

        code = generate_verification_code()
        verification = EmailVerificationCode(
            email=normalized_email,
            code_hash=hash_verification_code(normalized_email, code),
            purpose=REGISTER_PURPOSE,
            expires_at=datetime.now(UTC)
            + timedelta(minutes=settings.email_verification_expire_minutes),
        )
        self.db.add(verification)
        self.db.commit()
        self._send_email_code(normalized_email, code)
        return SendEmailVerificationResponse(
            message="验证码已发送。",
            expires_in_minutes=settings.email_verification_expire_minutes,
            resend_after_seconds=settings.email_verification_resend_seconds,
        )

    def register(self, payload: RegisterRequest) -> User:
        normalized_email = _normalize_email(str(payload.email))
        username = _normalize_username(payload.username)
        try:
            validate_password_strength(payload.password)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        self._ensure_email_available(normalized_email)
        self._ensure_username_available(username)
        self._consume_verification_code(normalized_email, payload.verification_code)

        avatar_seed = make_avatar_seed(username)
        user = User(
            email=normalized_email,
            username=username,
            password_hash=hash_password(payload.password),
            display_name=_normalize_optional_text(payload.display_name),
            role="user",
            is_active=True,
            is_email_verified=True,
            avatar_seed=avatar_seed,
            avatar_bg_color=make_avatar_color(f"{normalized_email}:{username}"),
        )
        self.db.add(user)
        self._commit_unique_user_change()
        self.db.refresh(user)
        return user

    def login(self, username: str, password: str, response: Response) -> User:
        user = self.db.scalar(select(User).where(User.username == username.strip()))
        if user is None or not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误。",
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="用户已被禁用。",
            )
        token, _ = create_access_token(user.id)
        user.last_login_at = datetime.now(UTC)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        response.set_cookie(
            key=settings.auth_cookie_name,
            value=token,
            max_age=settings.auth_token_expire_days * 24 * 60 * 60,
            httponly=True,
            secure=settings.auth_cookie_secure,
            samesite=settings.auth_cookie_samesite,
            path="/",
        )
        return user

    def logout(self, response: Response) -> None:
        response.delete_cookie(
            key=settings.auth_cookie_name,
            path="/",
            httponly=True,
            secure=settings.auth_cookie_secure,
            samesite=settings.auth_cookie_samesite,
        )

    def update_me(self, user: User, payload: UpdateMeRequest) -> User:
        updates = payload.model_dump(exclude_unset=True)
        if "username" in updates and updates["username"] is not None:
            username = _normalize_username(updates["username"])
            self._ensure_username_available(username, exclude_user_id=user.id)
            user.username = username
            user.avatar_seed = make_avatar_seed(username)
        if "display_name" in updates:
            user.display_name = _normalize_optional_text(updates["display_name"])
        self.db.add(user)
        self._commit_unique_user_change()
        self.db.refresh(user)
        return user

    def _ensure_email_available(self, email: str) -> None:
        if self.db.scalar(select(User.id).where(User.email == email)) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="邮箱已注册。",
            )

    def _ensure_username_available(
        self, username: str, exclude_user_id: UUID | None = None
    ) -> None:
        statement = select(User.id).where(User.username == username)
        if exclude_user_id is not None:
            statement = statement.where(User.id != exclude_user_id)
        if self.db.scalar(statement) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="用户名已存在。",
            )

    def _ensure_can_resend(self, email: str) -> None:
        latest = self.db.scalar(
            select(EmailVerificationCode)
            .where(
                EmailVerificationCode.email == email,
                EmailVerificationCode.purpose == REGISTER_PURPOSE,
            )
            .order_by(EmailVerificationCode.created_at.desc())
            .limit(1)
        )
        if latest is None:
            return
        elapsed = datetime.now(UTC) - latest.created_at
        if elapsed.total_seconds() < settings.email_verification_resend_seconds:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="验证码发送过于频繁，请稍后再试。",
            )

    def _consume_verification_code(self, email: str, code: str) -> None:
        verification = self.db.scalar(
            select(EmailVerificationCode)
            .where(
                EmailVerificationCode.email == email,
                EmailVerificationCode.purpose == REGISTER_PURPOSE,
                EmailVerificationCode.consumed_at.is_(None),
            )
            .order_by(EmailVerificationCode.created_at.desc())
            .limit(1)
        )
        if verification is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="验证码无效或已过期。",
            )
        now = datetime.now(UTC)
        if verification.expires_at <= now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="验证码无效或已过期。",
            )
        if verification.attempt_count >= MAX_VERIFICATION_ATTEMPTS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="验证码尝试次数过多。",
            )
        verification.attempt_count += 1
        if not verify_verification_code(email, code, verification.code_hash):
            self.db.add(verification)
            self.db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="验证码错误。",
            )
        verification.consumed_at = now
        self.db.add(verification)
        self.db.flush()

    def _send_email_code(self, email: str, code: str) -> None:
        if not settings.smtp_configured:
            logger.info("email_verification.dev_code email=%s code=%s", email, code)
            return
        message = EmailMessage()
        message["Subject"] = "邮箱验证码"
        message["From"] = settings.smtp_from_email or ""
        message["To"] = email
        message.set_content(
            f"您的验证码是：{code}，{settings.email_verification_expire_minutes} 分钟内有效。"
        )
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_username and settings.smtp_password:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)

    def _commit_unique_user_change(self) -> None:
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="邮箱或用户名已存在。",
            ) from exc


class UserService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_users(self) -> list[User]:
        return list(
            self.db.scalars(
                select(User).where(User.role != "admin").order_by(User.created_at.desc())
            )
        )

    def get_user(self, user_id: UUID, *, require_manageable: bool = False) -> User:
        user = self.db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在。")
        if require_manageable:
            self._ensure_manageable(user)
        return user

    def update_user(self, user_id: UUID, payload: AdminUserUpdateRequest) -> User:
        user = self.get_user(user_id)
        self._ensure_manageable(user)
        updates = payload.model_dump(exclude_unset=True)
        if "username" in updates and updates["username"] is not None:
            username = _normalize_username(updates["username"])
            AuthService(self.db)._ensure_username_available(username, exclude_user_id=user.id)
            user.username = username
            user.avatar_seed = make_avatar_seed(username)
        if "display_name" in updates:
            user.display_name = _normalize_optional_text(updates["display_name"])
        if "role" in updates and updates["role"] is not None:
            if updates["role"] not in MANAGEABLE_ROLES:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="角色不允许。")
            user.role = updates["role"]
        if "is_active" in updates and updates["is_active"] is not None:
            user.is_active = updates["is_active"]
        self.db.add(user)
        AuthService(self.db)._commit_unique_user_change()
        self.db.refresh(user)
        return user

    def _ensure_manageable(self, user: User) -> None:
        if user.role == "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="不能管理其他管理员。",
            )


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _normalize_username(username: str) -> str:
    normalized = username.strip()
    if not normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名不能为空。")
    return normalized


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None
