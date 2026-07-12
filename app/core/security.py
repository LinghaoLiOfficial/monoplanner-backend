import hashlib
import hmac
import re
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

ALGORITHM = "HS256"

AVATAR_COLORS = [
    "#2563eb",
    "#059669",
    "#dc2626",
    "#7c3aed",
    "#0891b2",
    "#c2410c",
    "#be123c",
    "#4f46e5",
]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def validate_password_strength(password: str) -> None:
    errors: list[str] = []
    if len(password) < 8:
        errors.append("至少 8 位")
    if not re.search(r"[A-Z]", password):
        errors.append("包含大写字母")
    if not re.search(r"[a-z]", password):
        errors.append("包含小写字母")
    if not re.search(r"\d", password):
        errors.append("包含数字")
    if not re.search(r"[^A-Za-z0-9]", password):
        errors.append("包含特殊字符")
    if errors:
        raise ValueError(f"密码强度不足，需要：{', '.join(errors)}。")


def generate_verification_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_verification_code(email: str, code: str) -> str:
    secret = _auth_secret()
    payload = f"{email.strip().lower()}:{code}".encode()
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def verify_verification_code(email: str, code: str, code_hash: str) -> bool:
    return hmac.compare_digest(hash_verification_code(email, code), code_hash)


def create_access_token(user_id: UUID) -> tuple[str, datetime]:
    expires_at = datetime.now(UTC) + timedelta(days=settings.auth_token_expire_days)
    token = jwt.encode(
        {"sub": str(user_id), "exp": expires_at},
        _auth_secret(),
        algorithm=ALGORITHM,
    )
    return token, expires_at


def decode_access_token(token: str) -> UUID:
    try:
        payload = jwt.decode(token, _auth_secret(), algorithms=[ALGORITHM])
        subject = payload.get("sub")
        if not isinstance(subject, str):
            raise ValueError
        return UUID(subject)
    except (JWTError, ValueError) as exc:
        raise ValueError("Invalid authentication token.") from exc


def make_avatar_seed(username: str) -> str:
    return username.strip()[:1].upper() or "U"


def make_avatar_color(seed: str) -> str:
    digest = hashlib.sha256(seed.encode()).digest()
    return AVATAR_COLORS[digest[0] % len(AVATAR_COLORS)]


def _auth_secret() -> str:
    if settings.auth_secret_key:
        return settings.auth_secret_key
    return "development-only-auth-secret"
