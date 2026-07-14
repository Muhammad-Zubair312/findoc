"""End-to-end graph run against the REAL Groq API (no mocking) — the "direct"
path needs no ingested document or Qdrant data, so it's a genuine full-pipeline
smoke test: query_analyzer -> router -> direct_llm -> generator -> grader ->
memory_writer, all with real LLM calls.

Skipped automatically if GROQ_API_KEY is a test placeholder (CI / no network).
"""

import uuid

import pytest

from app.agent.graph import get_graph
from app.agent.state import FinDocState
from app.config import settings

pytestmark = pytest.mark.asyncio

_requires_real_groq_key = pytest.mark.skipif(
    settings.GROQ_API_KEY in ("", "test-groq-key"),
    reason="No real GROQ_API_KEY configured — skipping live integration test.",
)


@_requires_real_groq_key
async def test_direct_query_runs_full_graph_live() -> None:
    graph = get_graph()
    state = FinDocState(
        query="What does EBITDA stand for?",
        document_ids=[],
        session_id=str(uuid.uuid4()),
        conversation_id=str(uuid.uuid4()),
    )

    result = await graph.ainvoke(state)

    assert result["strategy_used"] == "direct"
    assert result["query_type"] == "direct"
    assert len(result["answer"]) > 0
    assert result["faithfulness_score"] is not None
    assert isinstance(result["tokens_in"], int)
    assert isinstance(result["tokens_out"], int)
