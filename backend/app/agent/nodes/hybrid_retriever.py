"""LangGraph node running hybrid (Qdrant + BM25) retrieval. Used for cross_doc /
keyword queries, low router confidence, and as the fallback when Vectorless RAG
fails (force_hybrid_fallback)."""

import time
from typing import Any

from app.agent.state import FinDocState
from app.logging import get_logger
from app.retrieval.hybrid import HybridRetriever, hybrid_retriever

log = get_logger(__name__)


async def hybrid_retriever_node(
    state: FinDocState, retriever: HybridRetriever = hybrid_retriever
) -> dict[str, Any]:
    """Returns: { retrieved_sections, reasoning_trace, strategy_used }."""
    start = time.perf_counter()
    result = await retriever.retrieve(
        query=state.rewritten_query or state.query, document_ids=state.document_ids
    )
    log.info(
        "node_timing", node="hybrid_retriever", elapsed_secs=round(time.perf_counter() - start, 2)
    )
    return {
        "retrieved_sections": result.sections,
        "reasoning_trace": result.reasoning,
        "strategy_used": "hybrid",
    }
