"""Local cross-encoder reranker — no API cost. Scores (query, candidate) pairs and
returns candidates sorted by relevance."""

import asyncio

from sentence_transformers import CrossEncoder

from app.logging import get_logger

log = get_logger(__name__)

_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"


class CrossEncoderReranker:
    _model: CrossEncoder | None = None

    @classmethod
    def _get_model(cls) -> CrossEncoder:
        if cls._model is None:
            # First load (no local HF cache yet, e.g. a freshly (re)created
            # container with no persistent volume for it) took ~94s live —
            # see hybrid.py's rerank() timeout for why a single request can
            # never be blocked on this again.
            log.info("loading_reranker_model", model=_MODEL_NAME)
            cls._model = CrossEncoder(_MODEL_NAME, device="cpu")
        return cls._model

    def warm_up(self) -> None:
        """Pre-load model weights on startup to avoid paying this cost
        (spanning a full network download when uncached) on a user's first
        request. Mirrors LocalEmbedder.warm_up()."""
        self._get_model()

    async def rerank(self, query: str, candidates: list[str], top_n: int) -> list[int]:
        """Returns the indices of `candidates`, sorted descending by relevance to
        `query`, truncated to `top_n`."""
        if not candidates:
            return []

        model = self._get_model()
        pairs = [(query, candidate) for candidate in candidates]
        loop = asyncio.get_event_loop()
        # CrossEncoder.predict's stub signature is multimodal-generic; plain (str, str)
        # pairs are correct, well-documented usage for text reranking.
        scores = await loop.run_in_executor(None, lambda: model.predict(pairs))  # type: ignore[arg-type]

        ranked = sorted(range(len(candidates)), key=lambda i: scores[i], reverse=True)
        return ranked[:top_n]


reranker = CrossEncoderReranker()
