"""Hybrid retrieval — Qdrant dense search + in-memory BM25 sparse search, fused
with weighted Reciprocal Rank Fusion, then reranked by a local cross-encoder.
"""

import asyncio
import re
import uuid

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchAny
from rank_bm25 import BM25Okapi
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.state import Section
from app.config import settings
from app.db.models import Document, DocumentNode
from app.db.session import AsyncSessionLocal
from app.logging import get_logger
from app.retrieval.embedder import local_embedder
from app.retrieval.reranker import CrossEncoderReranker, reranker
from app.retrieval.types import RetrievalResult

log = get_logger(__name__)

_DENSE_WEIGHT = 0.7
_SPARSE_WEIGHT = 0.3
_RRF_K = 60
_FUSED_TOP_K = 6
_STUB_TEXT_CHAR_THRESHOLD = 300
_STUB_CHILD_COUNT_THRESHOLD = 3
_MAX_CHILDREN_PER_STUB = 8
_MAX_EXPANDED_NODES = 8
_RERANKED_TOP_N = 4
_RERANK_TIMEOUT_SECS = 5.0

# Company name → ticker. Used to narrow search when query names one company.
_COMPANY_ALIASES: dict[str, str] = {
    "nvidia": "NVDA",
    "nvda": "NVDA",
    "apple": "AAPL",
    "aapl": "AAPL",
    "tesla": "TSLA",
    "tsla": "TSLA",
    "microsoft": "MSFT",
    "msft": "MSFT",
}

# Keywords that signal a financial metric query — triggers title-based
# DB fallback to guarantee financial table nodes are in the candidate set.
_METRIC_KEYWORDS = [
    "r&d", "research", "spending", "expense", "expenses",
    "revenue", "income", "margin", "profit", "cost", "costs",
    "earnings", "ebitda", "operating",
]

# Node titles to always include when doing financial metric comparisons.
# These are the sections that store actual dollar figures in tables.
_FINANCIAL_TABLE_TITLES = [
    "%operating expense%",
    "%operating expenses%",       # matches Microsoft's "OPERATING EXPENSES"
    "%research and development%", # matches MSFT "Research and Development"
    "%results of operations%",
    "%consolidated statements of operations%",
]

NodeKey = tuple[str, str]  # (document_id, node_path)


def _detect_target_ticker(query: str) -> str | None:
    """Return ticker if query mentions exactly ONE company, else None."""
    words = re.findall(r'\b\w+\b', query.lower())
    found = {_COMPANY_ALIASES[w] for w in words if w in _COMPANY_ALIASES}
    return found.pop() if len(found) == 1 else None


def _detect_all_tickers(query: str) -> list[str]:
    """Return ALL unique tickers mentioned in the query."""
    words = re.findall(r'\b\w+\b', query.lower())
    found = list({_COMPANY_ALIASES[w] for w in words if w in _COMPANY_ALIASES})
    return found


def _is_metric_query(query: str) -> bool:
    """Return True if the query looks like a financial metric lookup."""
    q = query.lower()
    return any(kw in q for kw in _METRIC_KEYWORDS)


class HybridRetriever:
    def __init__(
        self,
        qdrant: AsyncQdrantClient | None = None,
        collection_name: str = settings.QDRANT_COLLECTION,
        cross_encoder: CrossEncoderReranker = reranker,
    ) -> None:
        self._qdrant = qdrant or AsyncQdrantClient(
            url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY or None
        )
        self._collection_name = collection_name
        self._reranker = cross_encoder
        self._bm25_cache: dict[str, BM25Okapi] = {}
        self._bm25_nodes_cache: dict[str, list[DocumentNode]] = {}

    async def retrieve(
        self, query: str, document_ids: list[str], k: int = 20
    ) -> RetrievalResult:
        embedding = await local_embedder.embed_one(query)

        async with AsyncSessionLocal() as db:
            ticker_by_doc_id = await self._load_ticker_map(db, document_ids)

        all_tickers = _detect_all_tickers(query)

        # ── Multi-company query ───────────────────────────────────────────────
        if len(all_tickers) >= 2:
            per_company_candidates: list[DocumentNode] = []
            seen_ids: set[uuid.UUID] = set()

            for ticker in all_tickers:
                target_doc_ids = [
                    doc_id for doc_id, t in ticker_by_doc_id.items()
                    if t == ticker
                ]
                if not target_doc_ids:
                    continue

                dense_hits = await self._dense_search(embedding, target_doc_ids, k)
                sparse_hits = await self._bm25_search(query, target_doc_ids, k)
                fused = _reciprocal_rank_fusion(dense_hits, sparse_hits)

                seen_keys: set[NodeKey] = {
                    (str(n.document_id), n.node_path)
                    for n in per_company_candidates
                }
                top_keys = [
                    key for key, _ in fused[:3]
                    if key not in seen_keys
                ]
                nodes = await self._load_nodes(top_keys)
                for n in nodes:
                    if n.id not in seen_ids:
                        seen_ids.add(n.id)
                        per_company_candidates.append(n)

                # Title-based DB fallback for financial metric queries.
                # Dense/BM25 miss financial table nodes (e.g. MSFT's
                # "Research and Development" child under "OPERATING EXPENSES")
                # because query terms don't match tokenised table text.
                if _is_metric_query(query):
                    async with AsyncSessionLocal() as db2:
                        title_nodes = await self._title_match_nodes(
                            db2, target_doc_ids
                        )
                    for n in title_nodes:
                        if n.id not in seen_ids:
                            seen_ids.add(n.id)
                            per_company_candidates.append(n)
                            log.info(
                                "hybrid_title_match_added",
                                ticker=ticker,
                                title=n.title,
                            )

                log.info(
                    "hybrid_per_company_search",
                    ticker=ticker,
                    candidates=len([
                        n for n in per_company_candidates
                        if ticker_by_doc_id.get(str(n.document_id)) == ticker
                    ]),
                )

            if not per_company_candidates:
                return RetrievalResult(
                    sections=[],
                    reasoning="No matching sections found.",
                    strategy="hybrid",
                )

            candidate_texts = [
                f"{n.title}\n{n.full_text}"[:2000]
                for n in per_company_candidates
            ]
            try:
                top_indices = await asyncio.wait_for(
                    self._reranker.rerank(
                        query,
                        candidate_texts,
                        # FIX 2: allow more slots so each company can appear.
                        # _RERANKED_TOP_N per company prevents one company
                        # crowding out the other entirely after reranking.
                        top_n=min(
                            _RERANKED_TOP_N * len(all_tickers),
                            len(per_company_candidates),
                        ),
                    ),
                    timeout=_RERANK_TIMEOUT_SECS,
                )
            except TimeoutError:
                log.warning(
                    "reranker_timeout_fallback",
                    candidate_count=len(per_company_candidates),
                )
                top_indices = list(
                    range(min(
                        _RERANKED_TOP_N * len(all_tickers),
                        len(per_company_candidates),
                    ))
                )

            top_nodes = [per_company_candidates[i] for i in top_indices]

            # FIX 3: Diversity guarantee — ensure every mentioned company
            # has at least one node in the final set. The cross-encoder can
            # rank one company's sections so much higher that the other
            # company is completely absent from top_nodes even though we
            # fetched candidates for it. If a company is missing, append
            # its best candidate from per_company_candidates.
            represented = {
                ticker_by_doc_id.get(str(n.document_id))
                for n in top_nodes
            }
            for ticker in all_tickers:
                if ticker not in represented:
                    fallback = next(
                        (
                            n for n in per_company_candidates
                            if ticker_by_doc_id.get(str(n.document_id)) == ticker
                        ),
                        None,
                    )
                    if fallback:
                        top_nodes.append(fallback)
                        log.info(
                            "hybrid_diversity_fallback_added",
                            ticker=ticker,
                        )

            async with AsyncSessionLocal() as db:
                top_nodes = await self._expand_stub_nodes(db, top_nodes)

            sections = [
                Section(
                    node_path=n.node_path,
                    title=n.title,
                    full_text=n.full_text,
                    page_start=n.page_start,
                    page_end=n.page_end,
                    document_id=str(n.document_id),
                    document_name=ticker_by_doc_id.get(
                        str(n.document_id), str(n.document_id)
                    ),
                )
                for n in top_nodes
            ]

            log.info(
                "hybrid_multi_company_retrieved",
                section_count=len(sections),
                docs=list({s.document_name for s in sections}),
            )

            return RetrievalResult(
                sections=sections,
                reasoning=(
                    f"Hybrid multi-company retrieval across "
                    f"{', '.join(all_tickers)}."
                ),
                strategy="hybrid",
            )

        # ── Single-company query ──────────────────────────────────────────────
        target_ticker = all_tickers[0] if len(all_tickers) == 1 else None
        if target_ticker:
            target_doc_ids = [
                doc_id for doc_id, ticker in ticker_by_doc_id.items()
                if ticker == target_ticker
            ]
            search_doc_ids = target_doc_ids if target_doc_ids else document_ids
            log.info(
                "hybrid_company_narrowed",
                target_ticker=target_ticker,
                search_doc_count=len(search_doc_ids),
            )
        else:
            search_doc_ids = document_ids

        dense_hits = await self._dense_search(embedding, search_doc_ids, k)
        sparse_hits = await self._bm25_search(query, search_doc_ids, k)

        fused = _reciprocal_rank_fusion(dense_hits, sparse_hits)
        top_keys = [key for key, _ in fused[:_FUSED_TOP_K]]

        candidates = await self._load_nodes(top_keys)
        if not candidates:
            return RetrievalResult(
                sections=[],
                reasoning="No matching sections found.",
                strategy="hybrid",
            )

        candidate_texts = [
            f"{n.title}\n{n.full_text}"[:2000] for n in candidates
        ]
        try:
            top_indices = await asyncio.wait_for(
                self._reranker.rerank(
                    query, candidate_texts, top_n=_RERANKED_TOP_N
                ),
                timeout=_RERANK_TIMEOUT_SECS,
            )
        except TimeoutError:
            log.warning(
                "reranker_timeout_fallback_to_rrf_order",
                timeout_secs=_RERANK_TIMEOUT_SECS,
                candidate_count=len(candidates),
            )
            top_indices = list(range(min(_RERANKED_TOP_N, len(candidates))))

        top_nodes = [candidates[i] for i in top_indices]

        async with AsyncSessionLocal() as db:
            top_nodes = await self._expand_stub_nodes(db, top_nodes)

        sections = [
            Section(
                node_path=n.node_path,
                title=n.title,
                full_text=n.full_text,
                page_start=n.page_start,
                page_end=n.page_end,
                document_id=str(n.document_id),
                document_name=ticker_by_doc_id.get(
                    str(n.document_id), str(n.document_id)
                ),
            )
            for n in top_nodes
        ]

        log.info(
            "hybrid_retrieved",
            section_count=len(sections),
            docs=list({s.document_name for s in sections}),
        )

        return RetrievalResult(
            sections=sections,
            reasoning=(
                f"Hybrid retrieval (dense + BM25 fusion, cross-encoder reranked) "
                f"over {len(search_doc_ids)} document(s)."
            ),
            strategy="hybrid",
        )

    async def _title_match_nodes(
        self, db: AsyncSession, document_ids: list[str]
    ) -> list[DocumentNode]:
        """Directly fetch financial table nodes by title.

        Bypasses BM25/dense limitations for queries like 'R&D spending'
        where the dollar figure lives in a table node that neither BM25
        (no stemming, tokenization issues) nor dense search reliably finds.
        """
        if not document_ids:
            return []
        result = await db.execute(
            select(DocumentNode).where(
                DocumentNode.document_id.in_(
                    [uuid.UUID(d) for d in document_ids]
                ),
                or_(
                    *[
                        DocumentNode.title.ilike(pattern)
                        for pattern in _FINANCIAL_TABLE_TITLES
                    ]
                ),
            ).limit(4)  # raised from 3 to 4 to catch both MSFT R&D + parent
        )
        return list(result.scalars().all())

    async def _dense_search(
        self, embedding: list[float], document_ids: list[str], k: int
    ) -> list[tuple[NodeKey, int]]:
        if not document_ids:
            return []
        response = await self._qdrant.query_points(
            collection_name=self._collection_name,
            query=embedding,
            query_filter=Filter(
                must=[
                    FieldCondition(
                        key="document_id", match=MatchAny(any=document_ids)
                    )
                ]
            ),
            limit=k,
        )
        hits: list[tuple[NodeKey, int]] = []
        for rank, point in enumerate(response.points):
            payload = point.payload or {}
            key = (str(payload["document_id"]), str(payload["node_path"]))
            hits.append((key, rank))
        return hits

    async def _bm25_search(
        self, query: str, document_ids: list[str], k: int
    ) -> list[tuple[NodeKey, int]]:
        if not document_ids:
            return []
        bm25, nodes = await self._get_bm25_index(document_ids)
        if bm25 is None or not nodes:
            return []

        scores = bm25.get_scores(query.split())
        ranked_indices = sorted(
            range(len(nodes)), key=lambda i: scores[i], reverse=True
        )[:k]

        hits: list[tuple[NodeKey, int]] = []
        for rank, idx in enumerate(ranked_indices):
            node = nodes[idx]
            hits.append(((str(node.document_id), node.node_path), rank))
        return hits

    async def _get_bm25_index(
        self, document_ids: list[str]
    ) -> tuple[BM25Okapi | None, list[DocumentNode]]:
        cache_key = ",".join(sorted(document_ids))
        if cache_key in self._bm25_cache:
            return self._bm25_cache[cache_key], self._bm25_nodes_cache[cache_key]

        async with AsyncSessionLocal() as db:
            nodes = list(
                (
                    await db.execute(
                        select(DocumentNode).where(
                            DocumentNode.document_id.in_(
                                [uuid.UUID(d) for d in document_ids]
                            )
                        )
                    )
                )
                .scalars()
                .all()
            )

        if not nodes:
            self._bm25_nodes_cache[cache_key] = nodes
            return None, nodes

        corpus = [node.full_text.split() for node in nodes]
        bm25 = BM25Okapi(corpus)
        self._bm25_cache[cache_key] = bm25
        self._bm25_nodes_cache[cache_key] = nodes
        return bm25, nodes

    async def _load_nodes(self, keys: list[NodeKey]) -> list[DocumentNode]:
        if not keys:
            return []
        doc_ids = {uuid.UUID(document_id) for document_id, _ in keys}
        async with AsyncSessionLocal() as db:
            nodes = (
                (
                    await db.execute(
                        select(DocumentNode).where(
                            DocumentNode.document_id.in_(doc_ids)
                        )
                    )
                )
                .scalars()
                .all()
            )
        nodes_by_key = {(str(n.document_id), n.node_path): n for n in nodes}
        return [nodes_by_key[key] for key in keys if key in nodes_by_key]

    async def _expand_stub_nodes(
        self, db: AsyncSession, nodes: list[DocumentNode]
    ) -> list[DocumentNode]:
        expanded: list[DocumentNode] = []
        seen_ids: set[uuid.UUID] = set()

        for node in nodes:
            children = await self._load_children(db, node)
            is_stub = (
                len(node.full_text.strip()) < _STUB_TEXT_CHAR_THRESHOLD
                or len(children) > _STUB_CHILD_COUNT_THRESHOLD
            )
            replacement = (
                children[:_MAX_CHILDREN_PER_STUB]
                if (is_stub and children)
                else [node]
            )
            for item in replacement:
                if item.id not in seen_ids:
                    seen_ids.add(item.id)
                    expanded.append(item)

        return expanded[:_MAX_EXPANDED_NODES]

    async def _load_children(
        self, db: AsyncSession, node: DocumentNode
    ) -> list[DocumentNode]:
        result = await db.execute(
            select(DocumentNode).where(
                DocumentNode.document_id == node.document_id,
                DocumentNode.parent_path == node.node_path,
            )
        )
        children = list(result.scalars().all())

        def _trailing_index(n: DocumentNode) -> int:
            try:
                return int(n.node_path.rsplit(".", 1)[-1])
            except ValueError:
                return 0

        children.sort(key=_trailing_index)
        return children

    async def _load_ticker_map(
        self, db: AsyncSession, document_ids: list[str]
    ) -> dict[str, str]:
        if not document_ids:
            return {}
        result = await db.execute(
            select(Document.id, Document.ticker, Document.filename).where(
                Document.id.in_([uuid.UUID(d) for d in document_ids])
            )
        )
        return {
            str(doc_id): (ticker or filename)
            for doc_id, ticker, filename in result.all()
        }


def _reciprocal_rank_fusion(
    dense_hits: list[tuple[NodeKey, int]],
    sparse_hits: list[tuple[NodeKey, int]],
) -> list[tuple[NodeKey, float]]:
    scores: dict[NodeKey, float] = {}
    for key, rank in dense_hits:
        scores[key] = scores.get(key, 0.0) + _DENSE_WEIGHT / (_RRF_K + rank + 1)
    for key, rank in sparse_hits:
        scores[key] = scores.get(key, 0.0) + _SPARSE_WEIGHT / (_RRF_K + rank + 1)
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)


hybrid_retriever = HybridRetriever()