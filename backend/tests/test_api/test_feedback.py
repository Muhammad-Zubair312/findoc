"""POST /feedback: score validation and message-ownership checks."""

import uuid

import pytest
from httpx import AsyncClient

from app.db.models import Conversation, Message
from app.db.session import AsyncSessionLocal

pytestmark = pytest.mark.asyncio


async def _register_and_login(client: AsyncClient) -> dict:
    email = f"user-{uuid.uuid4().hex[:12]}@example.com"
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "full_name": "Test User"},
    )
    assert resp.status_code == 201
    return resp.json()["user"]


async def _create_message_for_user(user_id: str) -> uuid.UUID:
    async with AsyncSessionLocal() as db:
        conv = Conversation(user_id=uuid.UUID(user_id), document_ids=[])
        db.add(conv)
        await db.flush()
        message = Message(conversation_id=conv.id, role="assistant", content="An answer.")
        db.add(message)
        await db.commit()
        await db.refresh(message)
        return message.id


async def test_feedback_requires_auth(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/feedback", json={"message_id": str(uuid.uuid4()), "score": 1})
    assert resp.status_code == 401


async def test_feedback_rejects_invalid_score(client: AsyncClient) -> None:
    user = await _register_and_login(client)
    message_id = await _create_message_for_user(user["id"])

    resp = await client.post("/api/v1/feedback", json={"message_id": str(message_id), "score": 5})
    assert resp.status_code == 422


async def test_feedback_accepts_upvote_and_downvote(client: AsyncClient) -> None:
    user = await _register_and_login(client)
    message_id = await _create_message_for_user(user["id"])

    up = await client.post("/api/v1/feedback", json={"message_id": str(message_id), "score": 1})
    assert up.status_code == 201
    assert up.json()["success"] is True

    message_id_2 = await _create_message_for_user(user["id"])
    down = await client.post(
        "/api/v1/feedback",
        json={"message_id": str(message_id_2), "score": -1, "reason_text": "Not helpful"},
    )
    assert down.status_code == 201


async def test_feedback_rejects_message_not_found(client: AsyncClient) -> None:
    await _register_and_login(client)
    resp = await client.post("/api/v1/feedback", json={"message_id": str(uuid.uuid4()), "score": 1})
    assert resp.status_code == 404


async def test_feedback_rejects_other_users_message(client: AsyncClient) -> None:
    owner = await _register_and_login(client)
    message_id = await _create_message_for_user(owner["id"])

    client.cookies.clear()
    await _register_and_login(client)
    resp = await client.post("/api/v1/feedback", json={"message_id": str(message_id), "score": 1})
    assert resp.status_code == 403
