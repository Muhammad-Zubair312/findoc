"""hybrid_retriever_node: thin wrapper around HybridRetriever.retrieve(), with a
stubbed retriever."""

import pytest

from app.agent.nodes.hybrid_retriever import hybrid_retriever_node
from app.agent.state import FinDocState, Section
from app.retrieval.types import RetrievalResult

pytestmark = pytest.mark.asyncio


class _FakeHybridRetriever:
    async def retrieve(self, query: str, document_ids: list[str], k: int = 20) -> RetrievalResult:
        section = Section(
            node_path="s1",
            title="Item 7",
            full_text="MD&A text",
            page_start=1,
            page_end=2,
            document_id=document_ids[0],
        )
        return RetrievalResult(
            sections=[section], reasoning="fused dense+sparse", strategy="hybrid"
        )


async def test_hybrid_retriever_node_returns_sections_and_strategy() -> None:
    state = FinDocState(
        query="Compare R&D spend",
        document_ids=["doc-1", "doc-2"],
        session_id="s",
        conversation_id="c",
    )
    update = await hybrid_retriever_node(state, retriever=_FakeHybridRetriever())  # type: ignore[arg-type]

    assert update["strategy_used"] == "hybrid"
    assert update["reasoning_trace"] == "fused dense+sparse"
    assert len(update["retrieved_sections"]) == 1
    assert update["retrieved_sections"][0].node_path == "s1"
