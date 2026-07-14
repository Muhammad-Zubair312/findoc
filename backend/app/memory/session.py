"""Redis-backed short-term session memory: the last few turns of a conversation,
used to give the generator conversational context without re-reading the full
Postgres message history on every turn."""

import json

from redis.asyncio import Redis

from app.config import settings

_SESSION_TTL_SECS = 3600  # 1 hour idle expiry
_MAX_TURNS = 5


def _key(session_id: str) -> str:
    return f"session_memory:{session_id}"


async def get_session_memory(session_id: str) -> str:
    """Returns a formatted block of recent turns, oldest first, or "" if none."""
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        raw_turns = await redis.lrange(  # type: ignore[misc]  # redis-py stub gap
            _key(session_id), 0, _MAX_TURNS - 1
        )
    finally:
        await redis.aclose()

    if not raw_turns:
        return ""

    turns = [json.loads(t) for t in reversed(raw_turns)]
    lines = ["PREVIOUS CONVERSATION TURNS:"]
    for turn in turns:
        lines.append(f"Q: {turn['query']}\nA: {turn['answer'][:300]}")
    return "\n".join(lines)


async def append_session_turn(session_id: str, query: str, answer: str) -> None:
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        payload = json.dumps({"query": query, "answer": answer})
        await redis.lpush(_key(session_id), payload)  # type: ignore[misc]  # redis-py stub gap
        await redis.ltrim(  # type: ignore[misc]  # redis-py stub gap
            _key(session_id), 0, _MAX_TURNS - 1
        )
        await redis.expire(_key(session_id), _SESSION_TTL_SECS)
    finally:
        await redis.aclose()
