"""SQLAlchemy 2 async ORM models — single source of truth for the schema.

Every table gets a UUID primary key (default=uuid4). Tables that are mutated after
creation (User, Document, Conversation) also get updated_at; append-only tables
(messages, feedback, eval results, refresh tokens, document trees) only get
created_at.
"""

import uuid
from datetime import date, datetime
from typing import Any, Literal

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class UUIDPkMixin:
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TimestampMixin(CreatedAtMixin):
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class User(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    plan: Mapped[str] = mapped_column(
        String(50), default="free", server_default="free", nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )

    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    documents: Mapped[list["Document"]] = relationship(back_populates="user")
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    feedback: Mapped[list["Feedback"]] = relationship(back_populates="user")


class RefreshToken(Base, UUIDPkMixin, CreatedAtMixin):
    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")


class Document(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "documents"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    ticker: Mapped[str | None] = mapped_column(String(20), nullable=True)
    filer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    filing_type: Mapped[Literal["10-K", "10-Q", "8-K", "other"]] = mapped_column(
        String(20), default="other", server_default="other", nullable=False
    )
    filing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    cik: Mapped[str | None] = mapped_column(String(20), nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    storage_key: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    # "deleted" = soft-delete marker (set by DELETE /documents/{id}); no separate
    # is_deleted column since this field already tracks document lifecycle state.
    ingest_status: Mapped[
        Literal["pending", "parsing", "tree_building", "embedding", "ready", "failed", "deleted"]
    ] = mapped_column(String(20), default="pending", server_default="pending", nullable=False)
    ingest_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="documents")
    tree: Mapped["DocumentTree | None"] = relationship(
        back_populates="document", cascade="all, delete-orphan", uselist=False
    )
    nodes: Mapped[list["DocumentNode"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentTree(Base, UUIDPkMixin):
    __tablename__ = "document_trees"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    tree_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    node_count: Mapped[int] = mapped_column(Integer, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    document: Mapped["Document"] = relationship(back_populates="tree")
    nodes: Mapped[list["DocumentNode"]] = relationship(back_populates="tree")


class DocumentNode(Base, UUIDPkMixin):
    __tablename__ = "document_nodes"
    __table_args__ = (Index("ix_document_nodes_document_id_node_path", "document_id", "node_path"),)

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    tree_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_trees.id"), nullable=False
    )
    node_path: Mapped[str] = mapped_column(String(500), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    full_text: Mapped[str] = mapped_column(Text, nullable=False)
    qdrant_point_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parent_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    document: Mapped["Document"] = relationship(back_populates="nodes")
    tree: Mapped["DocumentTree"] = relationship(back_populates="nodes")


class Conversation(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "conversations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    document_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list, server_default="{}", nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base, UUIDPkMixin, CreatedAtMixin):
    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[Literal["user", "assistant", "system"]] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    strategy_used: Mapped[str | None] = mapped_column(String(20), nullable=True)
    query_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    faithfulness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(
        Float, default=0.0, server_default="0.0", nullable=True
    )
    citations_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    reasoning_trace: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    is_incomplete: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    feedback: Mapped[list["Feedback"]] = relationship(
        back_populates="message", cascade="all, delete-orphan"
    )


class Feedback(Base, UUIDPkMixin, CreatedAtMixin):
    __tablename__ = "feedback"

    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    reason_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    message: Mapped["Message"] = relationship(back_populates="feedback")
    user: Mapped["User"] = relationship(back_populates="feedback")


class EvalRun(Base, UUIDPkMixin):
    __tablename__ = "eval_runs"

    dataset: Mapped[Literal["financebench", "custom"]] = mapped_column(String(20), nullable=False)
    run_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    correct_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    per_question_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    git_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    question_results: Mapped[list["EvalQuestionResult"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class EvalQuestionResult(Base, UUIDPkMixin):
    __tablename__ = "eval_question_results"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("eval_runs.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[str] = mapped_column(String(100), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    predicted_answer: Mapped[str] = mapped_column(Text, nullable=False)
    gold_answer: Mapped[str] = mapped_column(Text, nullable=False)
    correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    strategy_used: Mapped[str | None] = mapped_column(String(20), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retrieved_sections_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    run: Mapped["EvalRun"] = relationship(back_populates="question_results")
