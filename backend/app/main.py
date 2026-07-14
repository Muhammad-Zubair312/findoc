"""FastAPI entrypoint for FinDoc Intelligence."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sqlalchemy import text

from app.api import auth, chat, documents, eval, feedback, health
from app.config import settings
from app.db.session import engine
from app.logging import configure_logging, get_logger
from app.retrieval.embedder import local_embedder
from app.retrieval.reranker import reranker

configure_logging()
log = get_logger(__name__)

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENV,
        integrations=[FastApiIntegration()],
        traces_sample_rate=0.1,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    service_status: dict[str, str] = {}

    # DB
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        service_status["db"] = "ok"
    except Exception as exc:
        service_status["db"] = f"error: {exc}"
        log.error("startup_db_check_failed", error=str(exc))

    # Redis
    try:
        from redis.asyncio import Redis

        redis = Redis.from_url(settings.REDIS_URL)
        await redis.ping()
        await redis.aclose()
        service_status["redis"] = "ok"
    except Exception as exc:
        service_status["redis"] = f"error: {exc}"
        log.error("startup_redis_check_failed", error=str(exc))

    # Groq
    try:
        import httpx

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{settings.LLM_BASE_URL}/models",
                headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
            )
            if resp.status_code == 200:
                service_status["groq"] = "ok"
            else:
                service_status["groq"] = f"error: HTTP {resp.status_code}"
    except Exception as exc:
        service_status["groq"] = f"error: {exc}"
        log.error("startup_groq_check_failed", error=str(exc))

    # Local embedder
    try:
        local_embedder.warm_up()
        service_status["embedder"] = "ok"
    except Exception as exc:
        service_status["embedder"] = f"error: {exc}"
        log.error("startup_embedder_warmup_failed", error=str(exc))

    # Cross-encoder reranker
    try:
        reranker.warm_up()
        service_status["reranker"] = "ok"
    except Exception as exc:
        service_status["reranker"] = f"error: {exc}"
        log.error("startup_reranker_warmup_failed", error=str(exc))

    # Qdrant
    try:
        from qdrant_client import AsyncQdrantClient

        qdrant = AsyncQdrantClient(
            url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY or None
        )
        await qdrant.get_collections()
        await qdrant.close()
        service_status["qdrant"] = "ok"
    except Exception as exc:
        service_status["qdrant"] = f"error: {exc}"
        log.error("startup_qdrant_check_failed", error=str(exc))

    log.info("findoc_backend_ready", **service_status)

    yield

    await engine.dispose()
    log.info("findoc_backend_shutdown")


app = FastAPI(
    title="FinDoc Intelligence",
    version="1.0.0",
    docs_url="/docs" if settings.ENV != "prod" else None,
    redoc_url="/redoc" if settings.ENV != "prod" else None,
    openapi_url="/openapi.json" if settings.ENV != "prod" else None,
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# IMPORTANT: allow_credentials=True is INCOMPATIBLE with allow_origins=["*"].
# Browsers silently block credentialed POST requests (like login) when the
# server returns a wildcard origin — showing 0 bytes in the Network tab with
# no error message. Fix: always explicitly list allowed origins.
#
# After --force-recreate, CORS_ORIGINS env var may not load from the container
# environment before the middleware is registered. We hardcode the dev origins
# so login never silently fails regardless of env var state.
_DEV_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
]

_configured_origins: list[str] = (
    list(settings.CORS_ORIGINS)
    if settings.CORS_ORIGINS and settings.CORS_ORIGINS != ["*"]
    else []
)

# Merge dev origins into the configured list, deduplicating.
# In production, CORS_ORIGINS from .env takes priority and dev origins
# are still included (they are harmless — prod traffic never comes from
# localhost, and the browser's same-origin check is the real gatekeeper).
_all_origins: list[str] = list(
    dict.fromkeys(_configured_origins + _DEV_ORIGINS)
)

log.info("cors_origins_registered", origins=_all_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_all_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    log.error(
        "unhandled_exception",
        path=request.url.path,
        error=str(exc),
        exc_info=exc,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "internal_server_error",
                "message": "An unexpected error occurred.",
            }
        },
    )


app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(feedback.router, prefix="/api/v1")
app.include_router(eval.router, prefix="/api/v1")