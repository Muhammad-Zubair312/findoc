"""Creates the demo login (demo@findoc.local / demo1234) used by the frontend
quick-start and docs/VERIFICATION.md. Idempotent: skips if the user exists.

Must run before scripts/seed_sample_docs.py in bootstrap.sh — that script also
get-or-creates this same email, but with a random unusable password, so this
script has to win the race and create the row first.
"""

import asyncio

from sqlalchemy import select

from app.db.models import User
from app.db.session import AsyncSessionLocal
from app.security.auth import hash_password

_DEMO_EMAIL = "demo@findoc.local"
_DEMO_PASSWORD = "demo1234"


async def create_demo_user() -> None:
    async with AsyncSessionLocal() as db:
        existing = (
            await db.execute(select(User).where(User.email == _DEMO_EMAIL))
        ).scalar_one_or_none()
        if existing is not None:
            print(f"Demo user already exists: {_DEMO_EMAIL}")
            return

        user = User(
            email=_DEMO_EMAIL,
            hashed_password=hash_password(_DEMO_PASSWORD),
            full_name="Demo User",
        )
        db.add(user)
        await db.commit()

    print(f"Demo user ready: {_DEMO_EMAIL} / {_DEMO_PASSWORD}")


def main() -> None:
    asyncio.run(create_demo_user())


if __name__ == "__main__":
    main()
