"""Synchronous SQLAlchemy engine + session factory, used only by Celery workers.

Celery tasks are sync; async SQLAlchemy (asyncpg) is never used inside them. This
module gives Celery a plain psycopg2-backed session while the FastAPI app keeps using
the async engine in app.db.session.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings


def _sync_database_url() -> str:
    return settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql+psycopg2")


sync_engine = create_engine(_sync_database_url(), pool_size=5, max_overflow=10, pool_pre_ping=True)

SyncSessionLocal = sessionmaker(bind=sync_engine, expire_on_commit=False, class_=Session)


@contextmanager
def get_sync_db() -> Iterator[Session]:
    session = SyncSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
