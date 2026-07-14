"""Password hashing, JWT issuance/verification, and the get_current_user dependency."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, Request, WebSocket, status
from jose import ExpiredSignatureError, JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import User
from app.db.session import get_db

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

ACCESS_COOKIE_NAME = "findoc_access"
REFRESH_COOKIE_NAME = "findoc_refresh"
REFRESH_COOKIE_PATH = "/api/v1/auth/refresh"


def hash_password(password: str) -> str:
    return str(_pwd_context.hash(password))


def verify_password(password: str, hashed: str) -> bool:
    return bool(_pwd_context.verify(password, hashed))


def create_access_token(user_id: uuid.UUID) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_ACCESS_TTL_MIN),
    }
    return str(jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM))


def hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def generate_refresh_token() -> tuple[str, str, datetime]:
    """Returns (raw_token, token_hash, expires_at). The raw token goes to the client;
    only the hash is persisted."""
    raw_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(days=settings.JWT_REFRESH_TTL_DAYS)
    return raw_token, hash_refresh_token(raw_token), expires_at


def decode_access_token(token: str) -> dict[str, str]:
    try:
        payload: dict[str, str] = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
    except ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "token_expired", "message": "Access token has expired."},
        ) from exc
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_token", "message": "Invalid authentication credentials."},
        ) from exc
    return payload


def _extract_access_token(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.removeprefix("Bearer ")
    return request.cookies.get(ACCESS_COOKIE_NAME)


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    token = _extract_access_token(request)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "not_authenticated", "message": "Not authenticated."},
        )

    payload = decode_access_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_token", "message": "Invalid authentication credentials."},
        )

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_token", "message": "Invalid authentication credentials."},
        )
    return user


async def get_current_user_ws(
    websocket: WebSocket, token: str | None, db: AsyncSession
) -> User | None:
    """WebSocket variant of get_current_user: no Authorization header during the
    handshake, so the token comes from either an explicit query param or the
    httpOnly access cookie (sent automatically by the browser on the handshake
    request, same as any same-origin fetch — mirrors _extract_access_token's
    header-then-cookie fallback for REST). Failures return None instead of
    raising — the caller closes the socket with an appropriate close code
    rather than relying on an HTTP error response."""
    resolved_token = token or websocket.cookies.get(ACCESS_COOKIE_NAME)
    if not resolved_token:
        return None
    try:
        payload = decode_access_token(resolved_token)
    except HTTPException:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        return None
    return user
