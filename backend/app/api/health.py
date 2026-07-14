"""Health and readiness endpoints."""

from typing import Any

from fastapi import APIRouter
from qdrant_client import AsyncQdrantClient
from redis.asyncio import Redis
from sqlalchemy import text

from app.config import settings
from app.db.session import engine
from app.logging import get_logger
from app.retrieval.embedder import local_embedder

router = APIRouter(tags=["health"])
log = get_logger(__name__)


@router.get("/health")
async def health() -> dict[str, Any]:
    """Checks every downstream dependency and reports per-service status."""
    statuses: dict[str, str] = {}

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        statuses["db"] = "ok"
    except Exception as exc:
        statuses["db"] = f"error: {exc}"

    try:
        redis = Redis.from_url(settings.REDIS_URL)
        await redis.ping()  # type: ignore[misc]  # redis-py types ping() as Awaitable[bool] | bool
        await redis.aclose()
        statuses["redis"] = "ok"
    except Exception as exc:
        statuses["redis"] = f"error: {exc}"

    try:
        qdrant = AsyncQdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY or None,
        )
        await qdrant.get_collections()
        await qdrant.close()
        statuses["qdrant"] = "ok"
    except Exception as exc:
        statuses["qdrant"] = f"error: {exc}"

    try:
        import httpx

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{settings.LLM_BASE_URL}/models",
                headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
            )
            if resp.status_code == 200:
                statuses["groq"] = "ok"
            else:
                statuses["groq"] = f"error: HTTP {resp.status_code}"
    except Exception as exc:
        statuses["groq"] = f"error: {exc}"

    try:
        local_embedder.get_model()
        statuses["embedder"] = "ok"
    except Exception as exc:
        statuses["embedder"] = f"error: {exc}"

    overall_ok = all(v == "ok" for v in statuses.values())
    return {"status": "ok" if overall_ok else "degraded", **statuses}


@router.get("/ready")
async def ready() -> dict[str, str]:
    return {"status": "ok"}
