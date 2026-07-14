"""LangGraph node running Vectorless retrieval. Called only for
query_type="structural" (see app/agent/graph.py, section 2.6)."""

from typing import Any

from app.agent.state import FinDocState
from app.logging import get_logger
from app.retrieval.vectorless import vectorless_retriever

log = get_logger(__name__)


async def tree_navigator_node(state: FinDocState) -> dict[str, Any]:
    """Runs Vectorless retrieval across every document in scope.

    Returns: { retrieved_sections, reasoning_trace, strategy_used } on success, or
    { force_hybrid_fallback: True } if navigation fails for any document — this
    catches NavigationFailedError (invalid JSON, no path selected, etc.) AND any
    other exception the underlying LLM call can raise (e.g. a 413 "request too
    large" / token-per-minute rate-limit error from a large document's outline,
    hit live during the section 2.8 FinanceBench eval run). Vectorless RAG is
    explicitly a best-effort fast path with hybrid retrieval as the fallback —
    any failure mode should trigger that fallback, not just our own validation
    errors, or the whole graph run crashes instead of degrading gracefully.
    """
    results = []
    for doc_id in state.document_ids:
        try:
            result = await vectorless_retriever.retrieve(
                query=state.rewritten_query or state.query, document_id=doc_id
            )
            results.append(result)
        except Exception as exc:
            log.warning(
                "vectorless_navigation_failed", doc_id=doc_id, query=state.query, error=str(exc)
            )
            return {"force_hybrid_fallback": True}

    all_sections = [s for r in results for s in r.sections]
    reasoning = "\n\n".join(r.reasoning for r in results)
    return {
        "retrieved_sections": all_sections,
        "reasoning_trace": reasoning,
        "strategy_used": "vectorless",
    }
