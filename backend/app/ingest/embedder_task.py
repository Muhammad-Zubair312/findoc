"""Embeds every DocumentNode for a document (local model, no API cost) and upserts
the vectors into Qdrant, recording each node's assigned point id.

Like tree_builder, this takes an injected AsyncQdrantClient scoped to the calling
Celery task's single asyncio.run() — never the FastAPI app's long-lived singleton.
"""

import uuid
from uuid import uuid4

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PayloadSchemaType, PointStruct, VectorParams
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import DocumentNode
from app.logging import get_logger
from app.retrieval.embedder import local_embedder

log = get_logger(__name__)

_BATCH_SIZE = 32


async def _ensure_collection(qdrant: AsyncQdrantClient) -> None:
    collections = await qdrant.get_collections()
    existing = {c.name for c in collections.collections}
    if settings.QDRANT_COLLECTION not in existing:
        await qdrant.create_collection(
            collection_name=settings.QDRANT_COLLECTION,
            vectors_config=VectorParams(size=settings.EMBEDDING_DIM, distance=Distance.COSINE),
        )

    # Idempotent, checked every call (not just on first collection creation):
    # Qdrant Cloud rejects filtering on a payload field with no index —
    # HybridRetriever's dense search filters on document_id (app/retrieval/
    # hybrid.py) — so a collection created before this index existed (or by an
    # older version of this function) self-heals here rather than staying
    # broken. Hit this live during section 2.8's FinanceBench eval run.
    collection_info = await qdrant.get_collection(settings.QDRANT_COLLECTION)
    if "document_id" not in (collection_info.payload_schema or {}):
        await qdrant.create_payload_index(
            collection_name=settings.QDRANT_COLLECTION,
            field_name="document_id",
            field_schema=PayloadSchemaType.KEYWORD,
        )


async def embed_document(document_id: uuid.UUID, db: Session, qdrant: AsyncQdrantClient) -> None:
    """Embeds and upserts all DocumentNode rows for `document_id`, batching in
    groups of 32, and writes each node's assigned qdrant_point_id back to Postgres."""
    await _ensure_collection(qdrant)

    nodes = list(
        db.execute(select(DocumentNode).where(DocumentNode.document_id == document_id)).scalars()
    )
    if not nodes:
        log.warning("embed_document_no_nodes", document_id=str(document_id))
        return

    for batch_start in range(0, len(nodes), _BATCH_SIZE):
        batch = nodes[batch_start : batch_start + _BATCH_SIZE]
        texts = [f"{node.title}\n{node.full_text}"[:8000] for node in batch]
        embeddings = await local_embedder.embed(texts)

        points = []
        for node, embedding in zip(batch, embeddings, strict=True):
            point_id = str(uuid4())
            points.append(
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={
                        "document_id": str(node.document_id),
                        "node_path": node.node_path,
                        "title": node.title,
                        "page_start": node.page_start,
                        "page_end": node.page_end,
                    },
                )
            )
            node.qdrant_point_id = point_id

        await qdrant.upsert(collection_name=settings.QDRANT_COLLECTION, points=points)
        db.flush()

    log.info("embed_document_complete", document_id=str(document_id), node_count=len(nodes))
