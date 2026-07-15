"""Chat WebSocket (streaming graph runs) + conversations REST."""

import time
import uuid
from datetime import datetime
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from openai import RateLimitError
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import RetryError

from app.agent.graph import get_graph
from app.agent.state import FinDocState
from app.config import settings
from app.db.models import Conversation, Document, Message, User
from app.db.session import AsyncSessionLocal, get_db
from app.logging import get_logger
from app.security.auth import get_current_user, get_current_user_ws

router = APIRouter(tags=["chat"])
log = get_logger(__name__)

_STREAMING_LOCK_TTL_SECS = 300  # 5 min


# --- WebSocket ---


class ChatMessageIn(BaseModel):
    conversation_id: str | None = None
    message: str
    document_ids: list[str] = []
    session_id: str


def _user_facing_error_message(exc: BaseException) -> str:
    underlying: BaseException = exc
    if isinstance(exc, RetryError):
        last_attempt = exc.last_attempt
        if last_attempt is not None and last_attempt.exception() is not None:
            underlying = last_attempt.exception()  # type: ignore[assignment]

    if isinstance(underlying, RateLimitError):
        return (
            "Groq's free-tier quota is temporarily exhausted for this model. "
            "Please try again in a few minutes."
        )
    return "Something went wrong generating a response. Please try again."


async def _claim_streaming_lock(session_id: str) -> bool:
    redis = Redis.from_url(settings.REDIS_URL)
    try:
        acquired = await redis.set(
            f"chat_streaming:{session_id}", "1", nx=True, ex=_STREAMING_LOCK_TTL_SECS
        )
        return bool(acquired)
    finally:
        await redis.aclose()


async def _release_streaming_lock(session_id: str) -> None:
    redis = Redis.from_url(settings.REDIS_URL)
    try:
        await redis.delete(f"chat_streaming:{session_id}")
    finally:
        await redis.aclose()


async def _verify_document_ownership(db: AsyncSession, document_ids: list[str], user: User) -> None:
    if not document_ids:
        return
    doc_uuids = [uuid.UUID(d) for d in document_ids]
    docs = (await db.execute(select(Document).where(Document.id.in_(doc_uuids)))).scalars().all()
    found_ids = {str(d.id) for d in docs}
    missing = set(document_ids) - found_ids
    not_owned = [d for d in docs if d.user_id != user.id]
    if missing or not_owned:
        raise ValueError("One or more documents are inaccessible.")


async def _load_or_create_conversation(
    db: AsyncSession, user: User, conversation_id: str | None, document_ids: list[str]
) -> Conversation:
    if conversation_id:
        conv = await db.get(Conversation, uuid.UUID(conversation_id))
        if conv is None or conv.user_id != user.id:
            raise ValueError("Conversation not found.")
        return conv

    conv = Conversation(user_id=user.id, document_ids=[uuid.UUID(d) for d in document_ids])
    db.add(conv)
    await db.flush()
    return conv


def _citation_to_dict(c: Any) -> dict:
    """Safely convert citation to dict — handles Pydantic objects and plain dicts."""
    if hasattr(c, "model_dump"):
        return c.model_dump()
    if isinstance(c, dict):
        return c
    return {}


@router.websocket("/chat/ws")
async def chat_ws(websocket: WebSocket, token: str | None = None) -> None:
    async with AsyncSessionLocal() as db:
        user = await get_current_user_ws(websocket, token, db)

    if user is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="not_authenticated")
        return

    await websocket.accept()

    try:
        while True:
            raw = await websocket.receive_json()
            await _handle_chat_message(websocket, user, raw)
    except WebSocketDisconnect:
        pass


async def _handle_chat_message(websocket: WebSocket, user: User, raw: dict[str, Any]) -> None:
    try:
        body = ChatMessageIn(**raw)
    except Exception as exc:
        await websocket.send_json({"type": "error", "message": f"invalid_message: {exc}"})
        return

    if not await _claim_streaming_lock(body.session_id):
        await websocket.send_json({"type": "error", "message": "still_streaming"})
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="still_streaming")
        return

    try:
        async with AsyncSessionLocal() as db:
            try:
                await _verify_document_ownership(db, body.document_ids, user)
                conversation = await _load_or_create_conversation(
                    db, user, body.conversation_id, body.document_ids
                )
            except ValueError as exc:
                await websocket.send_json({"type": "error", "message": str(exc)})
                return

            user_message = Message(
                conversation_id=conversation.id, role="user", content=body.message
            )
            db.add(user_message)
            await db.commit()
            conversation_id = conversation.id

        await websocket.send_json({"type": "start", "strategy_predicted": None})
        await websocket.send_json({"type": "analyzing"})

        initial_state = FinDocState(
            query=body.message,
            document_ids=body.document_ids,
            session_id=body.session_id,
            conversation_id=str(conversation_id),
            user_id=str(user.id),
        )

        graph = get_graph()
        final_state: dict[str, Any] = {}
        streamed_content = ""
        start_time = time.perf_counter()

        try:
            async for mode, chunk in graph.astream(
                initial_state, stream_mode=["custom", "updates"]
            ):
                if mode == "custom":
                    custom_chunk = cast(dict[str, Any], chunk)
                    event_type = custom_chunk.get("type", "token")

                    # ── FIX: forward citations event directly to frontend ──
                    if event_type == "citations":
                        await websocket.send_json(custom_chunk)
                    else:
                        token_text = custom_chunk.get("content", "")
                        streamed_content += token_text
                        await websocket.send_json({"type": "token", "content": token_text})

                elif mode == "updates":
                    updates_chunk = cast(dict[str, dict[str, Any] | None], chunk)
                    for node_name, node_update in updates_chunk.items():
                        if not node_update:
                            continue
                        final_state.update(node_update)
                        if node_name in ("tree_navigator", "hybrid_retriever", "direct_llm"):
                            strategy = node_update.get("strategy_used")
                            if strategy:
                                await websocket.send_json({"type": "routing", "strategy": strategy})
                        elif node_name == "grader":
                            await websocket.send_json(
                                {
                                    "type": "grader",
                                    "faithfulness_score": node_update.get("faithfulness_score"),
                                    "retry": node_update.get("rewritten_query") is not None,
                                }
                            )
        except WebSocketDisconnect:
            await _save_message(
                conversation_id=conversation_id,
                content=streamed_content,
                final_state=final_state,
                latency_ms=(time.perf_counter() - start_time) * 1000,
                is_incomplete=True,
            )
            raise
        except Exception as exc:
            log.exception(
                "chat_graph_failed",
                conversation_id=str(conversation_id),
                session_id=body.session_id,
            )
            await websocket.send_json(
                {"type": "error", "message": _user_facing_error_message(exc)}
            )
            await _save_message(
                conversation_id=conversation_id,
                content=streamed_content,
                final_state=final_state,
                latency_ms=(time.perf_counter() - start_time) * 1000,
                is_incomplete=True,
            )
            return

        latency_ms = (time.perf_counter() - start_time) * 1000
        citations = final_state.get("citations", [])

        # ── FIX: safely handle both Pydantic objects and plain dicts ──
        await websocket.send_json(
            {
                "type": "citations",
                "citations": [_citation_to_dict(c) for c in citations],
            }
        )

        real_message_id = await _save_message(
            conversation_id=conversation_id,
            content=final_state.get("answer", streamed_content),
            final_state=final_state,
            latency_ms=latency_ms,
            is_incomplete=False,
        )

        await websocket.send_json(
            {
                "type": "end",
                "message_id": str(real_message_id),
                "latency_ms": round(latency_ms, 1),
                "tokens_in": final_state.get("tokens_in"),
                "tokens_out": final_state.get("tokens_out"),
                "strategy_used": final_state.get("strategy_used"),
            }
        )
    finally:
        await _release_streaming_lock(body.session_id)


async def _save_message(
    conversation_id: uuid.UUID,
    content: str,
    final_state: dict[str, Any],
    latency_ms: float,
    is_incomplete: bool,
) -> uuid.UUID:
    citations = final_state.get("citations", [])
    async with AsyncSessionLocal() as db:
        msg = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=content,
            strategy_used=final_state.get("strategy_used"),
            query_type=final_state.get("query_type"),
            faithfulness_score=final_state.get("faithfulness_score"),
            latency_ms=round(latency_ms),
            tokens_in=final_state.get("tokens_in"),
            tokens_out=final_state.get("tokens_out"),
            cost_usd=0.0,
            citations_json=[_citation_to_dict(c) for c in citations] if citations else None,
            reasoning_trace=final_state.get("reasoning_trace"),
            retry_count=final_state.get("retry_count", 0),
            is_incomplete=is_incomplete,
        )
        db.add(msg)
        await db.commit()
        await db.refresh(msg)
        return msg.id


# --- Conversations REST ---


class MessagePublic(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    strategy_used: str | None
    query_type: str | None
    faithfulness_score: float | None
    latency_ms: int | None
    tokens_in: int | None
    tokens_out: int | None
    cost_usd: float | None
    citations_json: Any | None
    reasoning_trace: str | None
    retry_count: int
    is_incomplete: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationPublic(BaseModel):
    id: uuid.UUID
    title: str | None
    document_ids: list[uuid.UUID]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationDetail(ConversationPublic):
    messages: list[MessagePublic]


class PaginatedConversations(BaseModel):
    items: list[ConversationPublic]
    total: int
    page: int
    page_size: int


class UpdateConversationTitleRequest(BaseModel):
    title: str


class DeleteResponse(BaseModel):
    success: bool


async def _get_owned_conversation(
    conversation_id: uuid.UUID, current_user: User, db: AsyncSession
) -> Conversation:
    conv = await db.get(Conversation, conversation_id)
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
    if conv.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your conversation.")
    return conv


class CreateConversationRequest(BaseModel):
    document_ids: list[str] = []


@router.post("/conversations", response_model=ConversationPublic, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    body: CreateConversationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationPublic:
    try:
        await _verify_document_ownership(db, body.document_ids, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    conv = Conversation(
        user_id=current_user.id,
        document_ids=[uuid.UUID(d) for d in body.document_ids],
    )
    db.add(conv)
    await db.flush()
    await db.refresh(conv)
    return ConversationPublic.model_validate(conv)


@router.get("/conversations", response_model=PaginatedConversations)
async def list_conversations(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedConversations:
    base_filter = Conversation.user_id == current_user.id

    total = (
        await db.execute(select(func.count()).select_from(Conversation).where(base_filter))
    ).scalar_one()

    result = await db.execute(
        select(Conversation)
        .where(base_filter)
        .order_by(Conversation.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [ConversationPublic.model_validate(c) for c in result.scalars().all()]
    return PaginatedConversations(items=items, total=total, page=page, page_size=page_size)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationDetail:
    conv = await _get_owned_conversation(conversation_id, current_user, db)
    messages = (
        (
            await db.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    return ConversationDetail(
        **ConversationPublic.model_validate(conv).model_dump(),
        messages=[MessagePublic.model_validate(m) for m in messages],
    )


@router.patch("/conversations/{conversation_id}", response_model=ConversationPublic)
async def update_conversation_title(
    conversation_id: uuid.UUID,
    body: UpdateConversationTitleRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationPublic:
    conv = await _get_owned_conversation(conversation_id, current_user, db)
    conv.title = body.title
    await db.flush()
    await db.refresh(conv)
    return ConversationPublic.model_validate(conv)


@router.delete("/conversations/{conversation_id}", response_model=DeleteResponse)
async def delete_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DeleteResponse:
    conv = await _get_owned_conversation(conversation_id, current_user, db)
    await db.delete(conv)
    await db.flush()
    return DeleteResponse(success=True)