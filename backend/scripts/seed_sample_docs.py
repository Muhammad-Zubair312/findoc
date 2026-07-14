"""Seeds the demo user (demo@findoc.local) with three real 10-Ks — Tesla, NVIDIA,
Apple — for empty-state UX and manual testing.

Rate-limit aware: 2s between EDGAR fetches (per-filing), plus tree_builder's own
INGEST_NODE_SUMMARY_DELAY_SECS between per-node LLM summary calls during
ingestion (~60 nodes/filing x 3 filings = ~180 calls, aggressively Redis-cached
so re-running this script is fast).
"""

import asyncio
import secrets

from sqlalchemy import select

from app.db.models import User
from app.db.session import AsyncSessionLocal
from app.ingest.edgar_fetcher import FilingType
from app.ingest.pipeline import ensure_document_for_ticker
from app.logging import get_logger
from app.security.auth import hash_password

log = get_logger(__name__)

_DEMO_USER_EMAIL = "demo@findoc.local"
_EDGAR_FETCH_DELAY_SECS = 2.0

# (ticker, form_type, year) — year is the EDGAR filingDate.year, i.e. when the
# filing covering that fiscal year was actually filed.
_SEED_FILINGS: list[tuple[str, FilingType, int]] = [
    ("TSLA", "10-K", 2024),  # Tesla FY2023 10-K, filed Jan 2024
    ("NVDA", "10-K", 2024),  # NVIDIA FY2024 10-K (fiscal year ends Jan), filed early 2024
    ("AAPL", "10-K", 2023),  # Apple FY2023 10-K (fiscal year ends Sep), filed Nov 2023
]


async def _get_or_create_demo_user() -> User:
    async with AsyncSessionLocal() as db:
        user = (
            await db.execute(select(User).where(User.email == _DEMO_USER_EMAIL))
        ).scalar_one_or_none()
        if user is not None:
            return user

        user = User(
            email=_DEMO_USER_EMAIL,
            hashed_password=hash_password(secrets.token_urlsafe(24)),
            full_name="Demo User",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


async def seed() -> None:
    user = await _get_or_create_demo_user()
    print(f"Demo user: {user.id} ({user.email})")

    for i, (ticker, form_type, year) in enumerate(_SEED_FILINGS):
        print(f"Ingesting {ticker} {form_type} ({year})...")
        try:
            document = await ensure_document_for_ticker(user.id, ticker, form_type, year)
            print(f"  -> document_id={document.id} status={document.ingest_status}")
        except Exception as exc:
            log.error("seed_document_failed", ticker=ticker, year=year, error=str(exc))
            print(f"  -> FAILED: {exc}")

        if i < len(_SEED_FILINGS) - 1:
            await asyncio.sleep(_EDGAR_FETCH_DELAY_SECS)

    print("Done.")


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()
