"""Local embeddings — ALL embeddings are generated locally. No API calls. No cost.

Uses BAAI/bge-base-en-v1.5 (768-dim) via sentence-transformers, run on CPU.
"""

import asyncio

from sentence_transformers import SentenceTransformer

from app.config import settings
from app.logging import get_logger

log = get_logger(__name__)


class LocalEmbedder:
    _model: SentenceTransformer | None = None

    @classmethod
    def get_model(cls) -> SentenceTransformer:
        if cls._model is None:
            log.info("loading_embedding_model", model=settings.EMBEDDING_MODEL)
            cls._model = SentenceTransformer(settings.EMBEDDING_MODEL, device="cpu")
        return cls._model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Encode texts in a thread pool to avoid blocking the event loop."""
        model = self.get_model()
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None,
            lambda: model.encode(texts, normalize_embeddings=True).tolist(),
        )
        return embeddings

    async def embed_one(self, text: str) -> list[float]:
        return (await self.embed([text]))[0]

    def warm_up(self) -> None:
        """Pre-load model weights on startup to avoid cold start."""
        self.get_model()


# Singleton
local_embedder = LocalEmbedder()
