"""Setup Qdrant collection for FinDoc.

Creates the QDRANT_COLLECTION with EMBEDDING_DIM-dim cosine vectors, matching
app/ingest/embedder_task.py's schema (including the document_id payload index
HybridRetriever's dense search filters on). Idempotent: safe to re-run.
"""

import asyncio

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PayloadSchemaType, VectorParams

from app.config import settings


async def main() -> None:
    client = AsyncQdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY or None)

    existing = await client.get_collections()
    names = {c.name for c in existing.collections}

    if settings.QDRANT_COLLECTION not in names:
        await client.create_collection(
            collection_name=settings.QDRANT_COLLECTION,
            vectors_config=VectorParams(size=settings.EMBEDDING_DIM, distance=Distance.COSINE),
        )
        print(
            f"Created collection '{settings.QDRANT_COLLECTION}' "
            f"({settings.EMBEDDING_DIM}-dim, cosine)"
        )
    else:
        print(f"Collection '{settings.QDRANT_COLLECTION}' already exists. Skipping creation.")

    collection_info = await client.get_collection(settings.QDRANT_COLLECTION)
    if "document_id" not in (collection_info.payload_schema or {}):
        await client.create_payload_index(
            collection_name=settings.QDRANT_COLLECTION,
            field_name="document_id",
            field_schema=PayloadSchemaType.KEYWORD,
        )
        print("Created payload index on 'document_id'")
    else:
        print("Payload index on 'document_id' already exists. Skipping.")


if __name__ == "__main__":
    asyncio.run(main())
