"""Shared pytest fixtures. Sets required env vars before any `app.*` import."""

import os

os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
# Local Docker Qdrant, not the real cloud instance in .env — keeps tests isolated
# from real data even though .env now has real QDRANT_URL/QDRANT_API_KEY for dev.
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("QDRANT_API_KEY", "")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://findoc:findoc@localhost:5433/findoc_test"
)
# DB index 1, separate from local dev's DB 0 — _reset_db flushes this on every test.
os.environ.setdefault("REDIS_URL", "redis://localhost:6380/1")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret")
os.environ.setdefault("LANGFUSE_ENABLED", "false")

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client():
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
async def _reset_db():
    """Creates all tables once, and truncates every table + flushes Redis after each test.

    Guards against the DATABASE_URL/REDIS_URL env vars above being no-ops: the
    `os.environ.setdefault()` calls only apply when running pytest outside Docker.
    Inside `docker-compose run backend pytest ...`, compose has already injected
    the real dev DATABASE_URL/REDIS_URL, so setdefault does nothing and this
    fixture would otherwise wipe dev data as teardown (as happened in practice).
    """
    from app.config import settings
    from app.db.models import Base
    from app.db.session import engine

    if "findoc_test" not in settings.DATABASE_URL:
        raise RuntimeError(
            "Refusing to run: DATABASE_URL does not point at a *_test database "
            f"(got {settings.DATABASE_URL!r}). This fixture truncates every table "
            "as teardown — running it against the dev/prod DB destroys data. "
            "Set DATABASE_URL to a dedicated test database before running pytest."
        )
    if not settings.REDIS_URL.rstrip("/").endswith(("/1", "/15")):
        raise RuntimeError(
            f"Refusing to run: REDIS_URL (got {settings.REDIS_URL!r}) doesn't look "
            "like a dedicated test DB index — this fixture flushes it as teardown."
        )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())

    from redis.asyncio import Redis

    redis = Redis.from_url(settings.REDIS_URL)
    await redis.flushdb()
    await redis.aclose()
