"""LangGraph node classifying the query's routing type: structural, cross_doc,
keyword, or direct. Runs first in the graph, feeding the router."""

import json
import uuid
from typing import Any

from sqlalchemy import select

from app.agent.state import FinDocState
from app.config import settings
from app.db.models import Document
from app.db.session import AsyncSessionLocal
from app.llm.llm_client import LLMClient, llm_client
from app.llm.prompts import QUERY_CLASSIFICATION_PROMPT
from app.logging import get_logger

log = get_logger(__name__)

_DEFAULT_QUERY_TYPE = "direct"
_DEFAULT_CONFIDENCE = 0.0


async def _document_summaries(document_ids: list[str]) -> str:
    if not document_ids:
        return "(no documents in scope)"

    async with AsyncSessionLocal() as db:
        docs = (
            (
                await db.execute(
                    select(Document).where(Document.id.in_([uuid.UUID(d) for d in document_ids]))
                )
            )
            .scalars()
            .all()
        )

    if not docs:
        return "(no documents in scope)"

    return "\n".join(
        f"- {d.ticker or d.filename} ({d.filing_type}, {d.filing_date or 'date unknown'})"
        for d in docs
    )


async def query_analyzer_node(state: FinDocState, llm: LLMClient = llm_client) -> dict[str, Any]:
    """Returns: { query_type, classifier_confidence }."""
    summaries = await _document_summaries(state.document_ids)
    prompt = QUERY_CLASSIFICATION_PROMPT.format(
        document_summaries=summaries, query=state.rewritten_query or state.query
    )

    try:
        content, _, _, _ = await llm.complete(
            model=settings.GROQ_FAST_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format={"type": "json_object"},
            trace_name="query_classification",
        )
        data = json.loads(content)
        query_type = data["type"]
        confidence = float(data["confidence"])
    except Exception as exc:
        log.warning("query_classification_failed", error=str(exc))
        query_type = _DEFAULT_QUERY_TYPE
        confidence = _DEFAULT_CONFIDENCE

    return {"query_type": query_type, "classifier_confidence": confidence}
