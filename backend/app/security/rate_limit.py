"""Redis-backed fixed-window rate limiter for FastAPI endpoints."""

from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import HTTPException, Request, status
from redis.asyncio import Redis

from app.config import settings

_redis: Redis | None = None


def _get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(settings.REDIS_URL)
    return _redis


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limiter(
    key_prefix: str, limit: int = 10, window_secs: int = 60
) -> Callable[[Request], Coroutine[Any, Any, None]]:
    """Returns a FastAPI dependency enforcing `limit` requests per IP per `window_secs`."""

    async def dependency(request: Request) -> None:
        redis = _get_redis()
        key = f"ratelimit:{key_prefix}:{_client_ip(request)}"
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, window_secs)
        if count > limit:
            ttl = await redis.ttl(key)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"code": "rate_limited", "message": "Too many requests."},
                headers={"Retry-After": str(max(ttl, 1))},
            )

    return dependency
