"""POST /feedback — user up/down votes on assistant messages."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Conversation, Feedback, Message, User
from app.db.session import get_db
from app.security.auth import get_current_user

router = APIRouter(tags=["feedback"])


# ── Original schema (kept for backward compat) ────────────────────────────────
class FeedbackRequest(BaseModel):
    message_id: uuid.UUID
    score: int
    reason_text: str | None = None

    @field_validator("score")
    @classmethod
    def validate_score(cls, v: int) -> int:
        if v not in (-1, 1):
            raise ValueError("score must be -1 or 1")
        return v


class FeedbackResponse(BaseModel):
    id: uuid.UUID
    success: bool


# ── Frontend schema — matches what MessageBubble.tsx actually sends ───────────
# Frontend calls: POST /messages/{message_id}/feedback
# Frontend body:  { "feedback": "up" | "down" }
class MessageFeedbackRequest(BaseModel):
    feedback: str  # "up" or "down"

    @field_validator("feedback")
    @classmethod
    def validate_feedback(cls, v: str) -> str:
        if v not in ("up", "down"):
            raise ValueError('feedback must be "up" or "down"')
        return v


# ── Route that matches the frontend exactly ───────────────────────────────────
@router.post(
    "/messages/{message_id}/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_message_feedback(
    message_id: uuid.UUID,
    body: MessageFeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FeedbackResponse:
    """Frontend-compatible feedback endpoint.

    Translates "up"/"down" → score 1/-1 and delegates to the same
    Feedback model used by the original /feedback route.
    """
    message = await db.get(Message, message_id)
    if message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found.",
        )

    conversation = await db.get(Conversation, message.conversation_id)
    if conversation is None or conversation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not your message.",
        )

    score = 1 if body.feedback == "up" else -1

    feedback = Feedback(
        message_id=message.id,
        user_id=current_user.id,
        score=score,
        reason_text=None,
    )
    db.add(feedback)
    await db.flush()
    await db.refresh(feedback)

    return FeedbackResponse(id=feedback.id, success=True)


# ── Original route (kept for eval pipeline / internal use) ───────────────────
@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_feedback(
    body: FeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FeedbackResponse:
    message = await db.get(Message, body.message_id)
    if message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found.",
        )

    conversation = await db.get(Conversation, message.conversation_id)
    if conversation is None or conversation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not your message.",
        )

    feedback = Feedback(
        message_id=message.id,
        user_id=current_user.id,
        score=body.score,
        reason_text=body.reason_text,
    )
    db.add(feedback)
    await db.flush()
    await db.refresh(feedback)

    return FeedbackResponse(id=feedback.id, success=True)