"""Router: a pass-through graph node reached after query_analyzer and again on
every grader retry loop-back. Its conditional edges (wired in app/agent/graph.py)
decide which retrieval node runs next.

route_decision() is the actual routing logic, used as the LangGraph conditional
edge function — kept separate from the node function so it's directly unit
testable without going through the graph.
"""

import uuid
from typing import Any

from sqlalchemy import select

from app.agent.state import FinDocState
from app.db.models import Document
from app.db.session import AsyncSessionLocal

CONFIDENCE_THRESHOLD = 0.7


async def router_node(state: FinDocState) -> dict[str, Any]:
    """Resolves an empty document_ids ("All documents" in the UI) to every
    ready document owned by the requesting user before routing. Qdrant's
    MatchAny([]) filter matches nothing (not everything), and BM25 has no
    corpus to search either, so an unresolved [] silently returns zero
    retrieved sections regardless of strategy."""
    if state.document_ids:
        return {}

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Document.id).where(
                Document.user_id == uuid.UUID(state.user_id),
                Document.ingest_status == "ready",
            )
        )
        all_ids = [str(doc_id) for doc_id in result.scalars().all()]

    return {"document_ids": all_ids}


def route_decision(state: FinDocState) -> str:
    """Returns the name of the next node: "tree_navigator", "direct_llm", or
    "hybrid_retriever"."""
    if state.retry_count > 0:
        return _route_retry(state)
    return _route_first_pass(state)


def _route_first_pass(state: FinDocState) -> str:
    if state.force_hybrid_fallback:
        return "hybrid_retriever"

    confidence = state.classifier_confidence or 0.0

    if (
        state.query_type == "structural"
        and len(state.document_ids) == 1
        and confidence >= CONFIDENCE_THRESHOLD
    ):
        return "tree_navigator"

    if state.query_type == "direct" and confidence >= CONFIDENCE_THRESHOLD:
        return "direct_llm"

    return "hybrid_retriever"


def _route_retry(state: FinDocState) -> str:
    """Flips strategy on retry: vectorless -> force hybrid; hybrid -> try
    vectorless (only viable for a single-document query; otherwise hybrid again)."""
    if state.strategy_used == "vectorless":
        return "hybrid_retriever"
    if state.strategy_used == "hybrid" and len(state.document_ids) == 1:
        return "tree_navigator"
    return "hybrid_retriever"
