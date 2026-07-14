"""Celery task orchestrating the full ingestion pipeline: parse -> build tree ->
embed. Celery tasks are sync; DB access uses the sync SQLAlchemy session
(app.db.sync_session), never the FastAPI app's async engine.

Async helpers (LLM, local embedder, Qdrant, storage, Redis pubsub) are all driven
from a single asyncio.run() call per task, using fresh client instances scoped to
that call — see the module docstrings on tree_builder.py and embedder_task.py for
why the FastAPI app's long-lived singletons can't be reused here.
"""

import asyncio
import json
import tempfile
import uuid
from pathlib import Path
from typing import Literal

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import FieldCondition, Filter, FilterSelector, MatchValue
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Document, DocumentNode, DocumentTree
from app.db.session import AsyncSessionLocal
from app.db.sync_session import get_sync_db
from app.ingest.edgar_fetcher import FilingType, fetch_filing
from app.ingest.embedder_task import embed_document
from app.ingest.pdf_parser import parse_pdf, parse_sec_html
from app.ingest.tree_builder import build_tree
from app.llm.llm_client import LLMClient
from app.logging import get_logger
from app.storage.r2 import storage_client
from app.workers.celery_app import celery_app

log = get_logger(__name__)

IngestStatus = Literal[
    "pending", "parsing", "tree_building", "embedding", "ready", "failed", "deleted"
]


async def _publish_progress(
    document_id: str, status: IngestStatus, error: str | None = None
) -> None:
    payload: dict[str, str] = {"status": status}
    if error:
        payload["error"] = error
    redis = AsyncRedis.from_url(settings.REDIS_URL)
    try:
        await redis.publish(f"doc_progress:{document_id}", json.dumps(payload))
    finally:
        await redis.aclose()


def _looks_like_pdf(data: bytes) -> bool:
    return data[:5] == b"%PDF-"


def _get_document_or_raise(db: Session, doc_uuid: uuid.UUID) -> Document:
    doc = db.get(Document, doc_uuid)
    if doc is None:
        raise ValueError(f"Document {doc_uuid} not found")
    return doc


def _set_status(doc_uuid: uuid.UUID, status: IngestStatus, **fields: object) -> None:
    with get_sync_db() as db:
        doc = _get_document_or_raise(db, doc_uuid)
        doc.ingest_status = status
        for name, value in fields.items():
            setattr(doc, name, value)


async def _ingest_document_async(document_id: str) -> None:
    doc_uuid = uuid.UUID(document_id)
    llm = LLMClient()
    qdrant = AsyncQdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY or None)

    try:
        with get_sync_db() as db:
            storage_key = _get_document_or_raise(db, doc_uuid).storage_key

        if not storage_key:
            raise ValueError(f"Document {document_id} has no storage_key")

        # --- parsing ---
        _set_status(doc_uuid, "parsing")
        await _publish_progress(document_id, "parsing")

        raw_bytes = await storage_client.download(storage_key)

        if _looks_like_pdf(raw_bytes):
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(raw_bytes)
                tmp_path = Path(tmp.name)
            try:
                sections = parse_pdf(tmp_path)
            finally:
                tmp_path.unlink(missing_ok=True)
        else:
            sections = parse_sec_html(raw_bytes)

        if not sections:
            raise ValueError("No sections could be extracted from this document")

        page_numbers = [s.page_end for s in sections if s.page_end is not None]
        page_count = max(page_numbers) if page_numbers else None

        # --- tree building ---
        _set_status(doc_uuid, "tree_building")
        await _publish_progress(document_id, "tree_building")

        with get_sync_db() as db:
            # Re-ingestion: DocumentTree.document_id is unique and
            # DocumentNode.tree_id has no ON DELETE CASCADE, so build_tree()'s
            # INSERT would otherwise hit a unique-constraint violation the
            # moment this document has been ingested before.
            existing_tree = db.execute(
                select(DocumentTree).where(DocumentTree.document_id == doc_uuid)
            ).scalar_one_or_none()
            if existing_tree is not None:
                db.execute(delete(DocumentNode).where(DocumentNode.tree_id == existing_tree.id))
                db.delete(existing_tree)
                db.flush()

            tree = await build_tree(sections, doc_uuid, db, llm)
            node_count = tree.node_count

        # --- embedding ---
        _set_status(doc_uuid, "embedding")
        await _publish_progress(document_id, "embedding")

        # Clear this document's old vectors first — the fresh DocumentNode
        # rows above have new UUIDs, so re-embedding would otherwise leave
        # the previous ingestion's points orphaned in Qdrant (matching
        # app/api/documents.py's delete_document, same filter pattern).
        try:
            await qdrant.delete(
                collection_name=settings.QDRANT_COLLECTION,
                points_selector=FilterSelector(
                    filter=Filter(
                        must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
                    )
                ),
            )
        except Exception as exc:
            log.warning("qdrant_pre_reingest_delete_failed", document_id=document_id, error=str(exc))

        with get_sync_db() as db:
            await embed_document(doc_uuid, db, qdrant)

        # --- ready ---
        _set_status(doc_uuid, "ready", page_count=page_count)
        await _publish_progress(document_id, "ready")

        log.info("ingest_document_complete", document_id=document_id, node_count=node_count)

    except Exception as exc:
        log.error("ingest_document_failed", document_id=document_id, error=str(exc))
        with get_sync_db() as db:
            doc = db.get(Document, doc_uuid)
            if doc is not None:
                doc.ingest_status = "failed"
                doc.ingest_error = str(exc)[:2000]
        await _publish_progress(document_id, "failed", error=str(exc))
        raise
    finally:
        await llm.aclose()
        await qdrant.close()


@celery_app.task(bind=True, max_retries=2, time_limit=1200)
def ingest_document(self: object, document_id: str) -> None:
    """Entry point invoked via `ingest_document.delay(str(document_id))`."""
    asyncio.run(_ingest_document_async(document_id))


async def ensure_document_for_ticker(
    user_id: uuid.UUID, ticker: str, form_type: FilingType, year: int
) -> Document:
    """Finds an existing ready Document matching (ticker, form_type, year) for
    `user_id`, or fetches it from SEC EDGAR, creates the row, uploads to
    storage, and runs the full ingestion pipeline — blocking until it's ready.

    Used by scripts/seed_sample_docs.py and app/eval/financebench_runner.py,
    which both need ingestion *complete* before proceeding, unlike the
    fire-and-forget POST /documents/edgar API endpoint (which just enqueues
    ingest_document.delay() and returns immediately).
    """
    async with AsyncSessionLocal() as db:
        candidates = (
            (
                await db.execute(
                    select(Document).where(
                        Document.user_id == user_id,
                        Document.ticker == ticker,
                        Document.filing_type == form_type,
                        Document.ingest_status == "ready",
                    )
                )
            )
            .scalars()
            .all()
        )
        for doc in candidates:
            if doc.filing_date and doc.filing_date.year == year:
                return doc

        filing = await fetch_filing(ticker, form_type, year)

        new_doc = Document(
            user_id=user_id,
            filename=filing.primary_document,
            ticker=filing.ticker,
            filer_name=filing.filer_name,
            filing_type=filing.filing_type,
            filing_date=filing.filing_date,
            cik=filing.cik,
            ingest_status="pending",
        )
        db.add(new_doc)
        await db.flush()

        ext = "pdf" if filing.content_type.startswith("application/pdf") else "html"
        storage_key = await storage_client.upload(
            key=f"{user_id}/{new_doc.id}.{ext}",
            data=filing.content,
            content_type=filing.content_type,
        )
        new_doc.storage_key = storage_key
        await db.commit()
        doc_id = new_doc.id

    await _ingest_document_async(str(doc_id))

    async with AsyncSessionLocal() as db:
        ingested = await db.get(Document, doc_id)
        if ingested is None or ingested.ingest_status != "ready":
            error = ingested.ingest_error if ingested else "document disappeared"
            raise RuntimeError(f"Ingestion failed for {ticker} {form_type} {year}: {error}")
        return ingested
