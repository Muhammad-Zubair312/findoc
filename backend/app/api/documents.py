"""Document CRUD, upload, EDGAR fetch, ingestion progress (SSE), sample-load."""

import json
import uuid
from collections.abc import AsyncGenerator
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import FieldCondition, Filter, FilterSelector, MatchValue
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Document, DocumentTree, User
from app.db.session import get_db
from app.ingest.edgar_fetcher import EdgarFilingNotFoundError, FilingType, fetch_filing
from app.logging import get_logger
from app.security.auth import get_current_user
from app.storage.r2 import storage_client
from app.workers.tasks import ingest_document

router = APIRouter(prefix="/documents", tags=["documents"])
log = get_logger(__name__)

_MAX_UPLOAD_BYTES = 20 * 1024 * 1024
_qdrant = AsyncQdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY or None)

_SAMPLE_TICKER = "TSLA"
_SAMPLE_FORM_TYPE: FilingType = "10-K"
_SAMPLE_YEAR = 2024  # Tesla's FY2023 10-K was filed in Jan 2024


class DocumentPublic(BaseModel):
    id: uuid.UUID
    filename: str
    ticker: str | None
    filer_name: str | None
    filing_type: str
    filing_date: date | None
    cik: str | None
    page_count: int | None
    ingest_status: str
    ingest_error: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TreeSummary(BaseModel):
    node_count: int
    ingested_at: datetime


class DocumentDetail(DocumentPublic):
    tree: TreeSummary | None = None


class PaginatedDocuments(BaseModel):
    items: list[DocumentPublic]
    total: int
    page: int
    page_size: int


class UploadResponse(BaseModel):
    document: DocumentPublic
    progress_url: str


class EdgarFetchRequest(BaseModel):
    ticker: str
    form_type: Literal["10-K", "10-Q", "8-K"]
    year: int


class DeleteResponse(BaseModel):
    success: bool


def _progress_url(document_id: uuid.UUID) -> str:
    return f"/api/v1/documents/{document_id}/progress"


async def _get_owned_document(
    document_id: uuid.UUID, current_user: User, db: AsyncSession
) -> Document:
    doc = await db.get(Document, document_id)
    if doc is None or doc.ingest_status == "deleted":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    if doc.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your document.")
    return doc


@router.get("", response_model=PaginatedDocuments)
async def list_documents(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedDocuments:
    base_filter = (Document.user_id == current_user.id) & (Document.ingest_status != "deleted")

    total = (
        await db.execute(select(func.count()).select_from(Document).where(base_filter))
    ).scalar_one()

    result = await db.execute(
        select(Document)
        .where(base_filter)
        .order_by(Document.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [DocumentPublic.model_validate(d) for d in result.scalars().all()]
    return PaginatedDocuments(items=items, total=total, page=page, page_size=page_size)


@router.get("/{document_id}", response_model=DocumentDetail)
async def get_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentDetail:
    doc = await _get_owned_document(document_id, current_user, db)
    tree_row = (
        await db.execute(select(DocumentTree).where(DocumentTree.document_id == document_id))
    ).scalar_one_or_none()
    tree_summary = (
        TreeSummary(node_count=tree_row.node_count, ingested_at=tree_row.ingested_at)
        if tree_row
        else None
    )
    return DocumentDetail(**DocumentPublic.model_validate(doc).model_dump(), tree=tree_summary)


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UploadResponse:
    raw_bytes = await file.read()

    if len(raw_bytes) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="File exceeds 20MB limit."
        )
    if raw_bytes[:5] != b"%PDF-":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="File does not look like a valid PDF."
        )

    doc = Document(
        user_id=current_user.id,
        filename=file.filename or "upload.pdf",
        filing_type="other",
        ingest_status="pending",
    )
    db.add(doc)
    await db.flush()

    storage_key = await storage_client.upload(
        key=f"{current_user.id}/{doc.id}.pdf", data=raw_bytes, content_type="application/pdf"
    )
    doc.storage_key = storage_key
    await db.flush()
    await db.refresh(doc)

    ingest_document.delay(str(doc.id))

    return UploadResponse(
        document=DocumentPublic.model_validate(doc), progress_url=_progress_url(doc.id)
    )


@router.post("/edgar", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def fetch_from_edgar(
    body: EdgarFetchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UploadResponse:
    try:
        filing = await fetch_filing(body.ticker, body.form_type, body.year)
    except EdgarFilingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    doc = Document(
        user_id=current_user.id,
        filename=filing.primary_document,
        ticker=filing.ticker,
        filer_name=filing.filer_name,
        filing_type=filing.filing_type,
        filing_date=filing.filing_date,
        cik=filing.cik,
        ingest_status="pending",
    )
    db.add(doc)
    await db.flush()

    ext = "pdf" if filing.content_type.startswith("application/pdf") else "html"
    storage_key = await storage_client.upload(
        key=f"{current_user.id}/{doc.id}.{ext}",
        data=filing.content,
        content_type=filing.content_type,
    )
    doc.storage_key = storage_key
    await db.flush()
    await db.refresh(doc)

    ingest_document.delay(str(doc.id))

    return UploadResponse(
        document=DocumentPublic.model_validate(doc), progress_url=_progress_url(doc.id)
    )


@router.post("/sample-load", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def sample_load(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UploadResponse:
    """Ingests the demo Tesla 10-K for empty-state UX."""
    body = EdgarFetchRequest(ticker=_SAMPLE_TICKER, form_type=_SAMPLE_FORM_TYPE, year=_SAMPLE_YEAR)
    return await fetch_from_edgar(body, current_user, db)


_PROGRESS_POLL_TIMEOUT_SECS = 1.0
_PROGRESS_MAX_DURATION_SECS = 1200  # matches ingest_document's Celery time_limit


@router.get("/{document_id}/progress")
async def document_progress(
    document_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    await _get_owned_document(document_id, current_user, db)

    async def event_stream() -> AsyncGenerator[str, None]:
        redis = Redis.from_url(settings.REDIS_URL)
        pubsub = redis.pubsub()
        try:
            await pubsub.subscribe(f"doc_progress:{document_id}")
            elapsed = 0.0
            while elapsed < _PROGRESS_MAX_DURATION_SECS:
                if await request.is_disconnected():
                    break
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=_PROGRESS_POLL_TIMEOUT_SECS
                )
                elapsed += _PROGRESS_POLL_TIMEOUT_SECS
                if message is None:
                    continue
                data = json.loads(message["data"])
                yield f"data: {json.dumps(data)}\n\n"
                if data.get("status") in ("ready", "failed"):
                    break
        finally:
            await pubsub.unsubscribe(f"doc_progress:{document_id}")
            await pubsub.aclose()  # type: ignore[no-untyped-call]  # redis-py stub gap
            await redis.aclose()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.delete("/{document_id}", response_model=DeleteResponse)
async def delete_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DeleteResponse:
    doc = await _get_owned_document(document_id, current_user, db)

    try:
        await _qdrant.delete(
            collection_name=settings.QDRANT_COLLECTION,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(key="document_id", match=MatchValue(value=str(document_id)))
                    ]
                )
            ),
        )
    except Exception as exc:
        log.warning("qdrant_delete_failed", document_id=str(document_id), error=str(exc))

    if doc.storage_key:
        try:
            await storage_client.delete(doc.storage_key)
        except Exception as exc:
            log.warning("storage_delete_failed", document_id=str(document_id), error=str(exc))

    doc.ingest_status = "deleted"
    await db.flush()

    return DeleteResponse(success=True)
