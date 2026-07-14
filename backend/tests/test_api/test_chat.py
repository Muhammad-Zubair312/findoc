"""Chat: streaming-lock/ownership/conversation helpers (unit), conversations REST
(API-layer), and one live end-to-end WS-message-handler test against the real
Groq API (needs no ingested document — a "direct" query).

WebSocket-transport-level testing (starlette.testclient.TestClient) is
deliberately NOT used here: its portal runs a different event loop than the
session-scoped one our async engine/redis singletons are already bound to once
other async tests have run in the same session — verified this actually breaks
(same class of bug fixed in 2.3's pytest-asyncio loop-scope change) before
choosing this approach. Testing _handle_chat_message directly with a fake
WebSocket keeps everything on the one shared event loop, consistent with every
other test in this suite.
"""

import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.api.chat import (
    _claim_streaming_lock,
    _handle_chat_message,
    _load_or_create_conversation,
    _release_streaming_lock,
    _verify_document_ownership,
)
from app.config import settings
from app.db.models import Conversation, Document, Message, User
from app.db.session import AsyncSessionLocal

pytestmark = pytest.mark.asyncio

_requires_real_groq_key = pytest.mark.skipif(
    settings.GROQ_API_KEY in ("", "test-groq-key"),
    reason="No real GROQ_API_KEY configured — skipping live integration test.",
)


async def _register_and_login(client: AsyncClient) -> dict[str, Any]:
    email = f"user-{uuid.uuid4().hex[:12]}@example.com"
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "full_name": "Test User"},
    )
    assert resp.status_code == 201
    return resp.json()["user"]  # type: ignore[no-any-return]


async def _create_user() -> User:
    async with AsyncSessionLocal() as db:
        user = User(
            email=f"chat-{uuid.uuid4().hex[:8]}@example.com",
            hashed_password="x",
            full_name="Test",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


class _FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def send_json(self, data: dict[str, Any]) -> None:
        self.sent.append(data)


class _DisconnectingWebSocket:
    """Raises WebSocketDisconnect after `disconnect_after` sends — simulates a
    client going away mid-stream."""

    def __init__(self, disconnect_after: int) -> None:
        self.sent: list[dict[str, Any]] = []
        self._disconnect_after = disconnect_after

    async def send_json(self, data: dict[str, Any]) -> None:
        from fastapi import WebSocketDisconnect

        if len(self.sent) >= self._disconnect_after:
            raise WebSocketDisconnect(code=1001)
        self.sent.append(data)


# --- streaming lock ---


async def test_streaming_lock_claim_and_release() -> None:
    session_id = str(uuid.uuid4())
    assert await _claim_streaming_lock(session_id) is True
    assert await _claim_streaming_lock(session_id) is False

    await _release_streaming_lock(session_id)
    assert await _claim_streaming_lock(session_id) is True

    await _release_streaming_lock(session_id)


# --- document ownership ---


async def test_verify_document_ownership_passes_for_owned_docs() -> None:
    user = await _create_user()
    async with AsyncSessionLocal() as db:
        doc = Document(user_id=user.id, filename="f.pdf", ingest_status="ready")
        db.add(doc)
        await db.commit()
        await db.refresh(doc)

        await _verify_document_ownership(db, [str(doc.id)], user)  # no raise


async def test_verify_document_ownership_rejects_missing_doc() -> None:
    user = await _create_user()
    async with AsyncSessionLocal() as db:
        with pytest.raises(ValueError):
            await _verify_document_ownership(db, [str(uuid.uuid4())], user)


async def test_verify_document_ownership_rejects_other_users_doc() -> None:
    owner = await _create_user()
    other = await _create_user()
    async with AsyncSessionLocal() as db:
        doc = Document(user_id=owner.id, filename="f.pdf", ingest_status="ready")
        db.add(doc)
        await db.commit()
        await db.refresh(doc)

        with pytest.raises(ValueError):
            await _verify_document_ownership(db, [str(doc.id)], other)


# --- load or create conversation ---


async def test_load_or_create_conversation_creates_new_when_none() -> None:
    user = await _create_user()
    async with AsyncSessionLocal() as db:
        conv = await _load_or_create_conversation(db, user, None, [])
        await db.commit()
        assert conv.user_id == user.id


async def test_load_or_create_conversation_loads_existing() -> None:
    user = await _create_user()
    async with AsyncSessionLocal() as db:
        conv = Conversation(user_id=user.id, document_ids=[])
        db.add(conv)
        await db.commit()
        await db.refresh(conv)
        conv_id = conv.id

    async with AsyncSessionLocal() as db:
        loaded = await _load_or_create_conversation(db, user, str(conv_id), [])
        assert loaded.id == conv_id


async def test_load_or_create_conversation_rejects_other_users_conversation() -> None:
    owner = await _create_user()
    other = await _create_user()
    async with AsyncSessionLocal() as db:
        conv = Conversation(user_id=owner.id, document_ids=[])
        db.add(conv)
        await db.commit()
        await db.refresh(conv)
        conv_id = conv.id

    async with AsyncSessionLocal() as db:
        with pytest.raises(ValueError):
            await _load_or_create_conversation(db, other, str(conv_id), [])


# --- conversations REST ---


async def test_list_conversations_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/conversations")
    assert resp.status_code == 401


async def test_conversation_lifecycle_via_rest(client: AsyncClient) -> None:
    user_public = await _register_and_login(client)

    async with AsyncSessionLocal() as db:
        conv = Conversation(user_id=uuid.UUID(user_public["id"]), document_ids=[])
        db.add(conv)
        await db.commit()
        await db.refresh(conv)
        conv_id = conv.id

    list_resp = await client.get("/api/v1/conversations")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    get_resp = await client.get(f"/api/v1/conversations/{conv_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["messages"] == []

    patch_resp = await client.patch(f"/api/v1/conversations/{conv_id}", json={"title": "New title"})
    assert patch_resp.status_code == 200
    assert patch_resp.json()["title"] == "New title"

    delete_resp = await client.delete(f"/api/v1/conversations/{conv_id}")
    assert delete_resp.status_code == 200
    assert delete_resp.json() == {"success": True}

    get_after_delete = await client.get(f"/api/v1/conversations/{conv_id}")
    assert get_after_delete.status_code == 404


async def test_conversation_forbidden_for_non_owner(client: AsyncClient) -> None:
    owner_public = await _register_and_login(client)
    async with AsyncSessionLocal() as db:
        conv = Conversation(user_id=uuid.UUID(owner_public["id"]), document_ids=[])
        db.add(conv)
        await db.commit()
        await db.refresh(conv)
        conv_id = conv.id

    client.cookies.clear()
    await _register_and_login(client)
    resp = await client.get(f"/api/v1/conversations/{conv_id}")
    assert resp.status_code == 403


# --- live end-to-end WS message handling ---


@_requires_real_groq_key
async def test_handle_chat_message_live_direct_query_persists_messages() -> None:
    user = await _create_user()
    ws = _FakeWebSocket()
    session_id = str(uuid.uuid4())

    await _handle_chat_message(
        ws,  # type: ignore[arg-type]
        user,
        {
            "conversation_id": None,
            "message": "What does EBITDA stand for?",
            "document_ids": [],
            "session_id": session_id,
        },
    )

    event_types = [e["type"] for e in ws.sent]
    assert event_types[0] == "start"
    assert event_types[1] == "analyzing"
    assert "routing" in event_types
    assert "token" in event_types
    assert "grader" in event_types
    assert event_types[-2] == "citations"
    assert event_types[-1] == "end"

    end_event = ws.sent[-1]
    assert end_event["strategy_used"] == "direct"
    assert isinstance(end_event["tokens_in"], int)

    # streaming lock must be released after handling completes
    assert await _claim_streaming_lock(session_id) is True
    await _release_streaming_lock(session_id)

    messages = await _fetch_messages_for_user(user.id)
    assert [m.role for m in messages] == ["user", "assistant"]
    assert messages[0].content == "What does EBITDA stand for?"
    assert messages[1].strategy_used == "direct"
    assert messages[1].is_incomplete is False
    assert messages[1].tokens_in is not None


async def _fetch_messages_for_user(user_id: uuid.UUID) -> list[Message]:
    async with AsyncSessionLocal() as db:
        conv = (
            (await db.execute(select(Conversation).where(Conversation.user_id == user_id)))
            .scalars()
            .first()
        )
        assert conv is not None
        result = await db.execute(
            select(Message).where(Message.conversation_id == conv.id).order_by(Message.created_at)
        )
        return list(result.scalars().all())


@_requires_real_groq_key
async def test_disconnect_mid_stream_saves_partial_incomplete_message() -> None:
    from fastapi import WebSocketDisconnect

    user = await _create_user()
    # start(1) + analyzing(1) + routing(1) + a couple of tokens(2), then disconnect
    ws = _DisconnectingWebSocket(disconnect_after=5)
    session_id = str(uuid.uuid4())

    with pytest.raises(WebSocketDisconnect):
        await _handle_chat_message(
            ws,  # type: ignore[arg-type]
            user,
            {
                "conversation_id": None,
                "message": "What does EBITDA stand for?",
                "document_ids": [],
                "session_id": session_id,
            },
        )

    # lock must still be released even though the handler raised
    assert await _claim_streaming_lock(session_id) is True
    await _release_streaming_lock(session_id)

    messages = await _fetch_messages_for_user(user.id)
    assert [m.role for m in messages] == ["user", "assistant"]
    assert messages[1].is_incomplete is True

    # The token that triggers the disconnect is accumulated into streamed_content
    # before the (failing) send attempt, so the saved partial content is the sent
    # tokens plus possibly one more in flight — assert the prefix relationship,
    # not exact equality.
    sent_tokens = "".join(e["content"] for e in ws.sent if e["type"] == "token")
    assert messages[1].content.startswith(sent_tokens)
    assert len(messages[1].content) > 0
    assert len(messages[1].content) < 200  # genuinely partial, not the full answer
