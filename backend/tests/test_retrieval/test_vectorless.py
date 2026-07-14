"""Vectorless RAG: tree navigation against a fixture tree, with a stubbed LLM
client so no real Groq call is made."""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from app.agent.nodes.tree_navigator import tree_navigator_node
from app.agent.state import FinDocState
from app.db.models import Document, DocumentNode, DocumentTree, User
from app.db.session import AsyncSessionLocal
from app.retrieval.types import RetrievalResult
from app.retrieval.vectorless import NavigationFailedError, VectorlessRetriever

pytestmark = pytest.mark.asyncio


class _FakeLLMClient:
    """Duck-types LLMClient.complete(); returns canned responses in sequence."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = responses
        self.call_count = 0

    async def complete(self, **kwargs: Any) -> tuple[str, int, int, float]:
        content = self._responses[min(self.call_count, len(self._responses) - 1)]
        self.call_count += 1
        return content, 10, 10, 5.0


def _build_fixture_tree() -> dict[str, Any]:
    """4 top-level sections x 4 children = 20 nodes, matching tree_builder's
    node_path scheme ("s1", "s1.1", ...)."""

    def leaf(node_id: str, title: str) -> dict[str, Any]:
        return {
            "node_id": node_id,
            "title": title,
            "summary": f"Summary of {title}.",
            "page_range": [1, 2],
            "children": [],
        }

    top_titles = ["Item 1. Business", "Item 1A. Risk Factors", "Item 7. MD&A", "Item 8. Financials"]
    children = []
    for i, title in enumerate(top_titles, start=1):
        sub_children = [leaf(f"s{i}.{j}", f"{title} - Subsection {j}") for j in range(1, 5)]
        children.append(
            {
                "node_id": f"s{i}",
                "title": title,
                "summary": f"Summary of {title}.",
                "page_range": [1, 10],
                "children": sub_children,
            }
        )

    return {
        "root": {
            "node_id": "root",
            "title": "Document Root",
            "summary": "",
            "page_range": [1, 40],
            "children": children,
        }
    }


async def _seed_document_with_tree() -> str:
    tree_json = _build_fixture_tree()

    async with AsyncSessionLocal() as db:
        user = User(
            email=f"vectorless-{uuid.uuid4().hex[:8]}@example.com",
            hashed_password="x",
            full_name="Test",
        )
        db.add(user)
        await db.flush()

        document = Document(user_id=user.id, filename="fixture.pdf", ingest_status="ready")
        db.add(document)
        await db.flush()

        tree = DocumentTree(
            document_id=document.id,
            tree_json=tree_json,
            node_count=20,
            ingested_at=datetime.now(UTC),
        )
        db.add(tree)
        await db.flush()

        def flatten(node: dict[str, Any]) -> list[dict[str, Any]]:
            out = [node] if node["node_id"] != "root" else []
            for child in node.get("children", []):
                out.extend(flatten(child))
            return out

        for node in flatten(tree_json["root"]):
            db.add(
                DocumentNode(
                    document_id=document.id,
                    tree_id=tree.id,
                    node_path=node["node_id"],
                    title=node["title"],
                    summary=node["summary"],
                    page_start=node["page_range"][0],
                    page_end=node["page_range"][1],
                    full_text=f"Full text for {node['title']}. " * 20,
                )
            )
        await db.commit()

        return str(document.id)


async def test_happy_path_selects_correct_sections() -> None:
    document_id = await _seed_document_with_tree()
    fake_llm = _FakeLLMClient(
        [
            '{"reasoning": "Revenue and margin data live in Item 7.", '
            '"selected_node_paths": ["s3.1", "s3.2"]}'
        ]
    )
    retriever = VectorlessRetriever(llm=fake_llm)  # type: ignore[arg-type]

    result = await retriever.retrieve("What was gross margin?", document_id)

    assert result.strategy == "vectorless"
    assert {s.node_path for s in result.sections} == {"s3.1", "s3.2"}
    assert "Item 7" in result.reasoning
    assert fake_llm.call_count == 1


async def test_invalid_json_twice_raises_navigation_failed() -> None:
    document_id = await _seed_document_with_tree()
    fake_llm = _FakeLLMClient(["not json at all", "still not json"])
    retriever = VectorlessRetriever(llm=fake_llm)  # type: ignore[arg-type]

    with pytest.raises(NavigationFailedError):
        await retriever.retrieve("What was gross margin?", document_id)

    assert fake_llm.call_count == 2


async def test_invalid_node_path_is_skipped_not_fatal() -> None:
    document_id = await _seed_document_with_tree()
    fake_llm = _FakeLLMClient(
        [
            '{"reasoning": "Mix of valid and invalid paths.", '
            '"selected_node_paths": ["s3.1", "nonexistent.path"]}'
        ]
    )
    retriever = VectorlessRetriever(llm=fake_llm)  # type: ignore[arg-type]

    result = await retriever.retrieve("What was gross margin?", document_id)

    assert [s.node_path for s in result.sections] == ["s3.1"]


async def test_empty_selection_raises_navigation_failed() -> None:
    document_id = await _seed_document_with_tree()
    fake_llm = _FakeLLMClient(['{"reasoning": "Nothing matches.", "selected_node_paths": []}'])
    retriever = VectorlessRetriever(llm=fake_llm)  # type: ignore[arg-type]

    with pytest.raises(NavigationFailedError):
        await retriever.retrieve("Unrelated question", document_id)


async def test_missing_document_tree_raises_navigation_failed() -> None:
    fake_llm = _FakeLLMClient(["{}"])
    retriever = VectorlessRetriever(llm=fake_llm)  # type: ignore[arg-type]

    with pytest.raises(NavigationFailedError):
        await retriever.retrieve("query", str(uuid.uuid4()))


async def test_tree_navigator_node_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.agent.nodes.tree_navigator as mod

    async def fake_retrieve(query: str, document_id: str) -> RetrievalResult:
        return RetrievalResult(sections=[], reasoning="ok", strategy="vectorless")

    monkeypatch.setattr(mod.vectorless_retriever, "retrieve", fake_retrieve)

    state = FinDocState(
        query="What was revenue?",
        document_ids=["doc-1"],
        session_id="sess-1",
        conversation_id="conv-1",
    )
    update = await tree_navigator_node(state)

    assert update["strategy_used"] == "vectorless"
    assert update["reasoning_trace"] == "ok"
    assert update["retrieved_sections"] == []


async def test_tree_navigator_node_sets_hybrid_fallback_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.agent.nodes.tree_navigator as mod

    async def failing_retrieve(query: str, document_id: str) -> RetrievalResult:
        raise NavigationFailedError("boom")

    monkeypatch.setattr(mod.vectorless_retriever, "retrieve", failing_retrieve)

    state = FinDocState(
        query="What was revenue?",
        document_ids=["doc-1"],
        session_id="sess-1",
        conversation_id="conv-1",
    )
    update = await tree_navigator_node(state)

    assert update == {"force_hybrid_fallback": True}


async def test_tree_navigator_node_falls_back_on_non_navigation_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A generic exception from the underlying LLM call (e.g. a 413 "request too
    large" / token-per-minute rate-limit error from Groq, hit live during a real
    FinanceBench eval run against a large document) must ALSO trigger the hybrid
    fallback, not just our own NavigationFailedError — otherwise the whole graph
    run crashes instead of degrading gracefully."""
    import app.agent.nodes.tree_navigator as mod

    async def failing_retrieve(query: str, document_id: str) -> RetrievalResult:
        raise RuntimeError("413: request too large for tokens per minute")

    monkeypatch.setattr(mod.vectorless_retriever, "retrieve", failing_retrieve)

    state = FinDocState(
        query="What was revenue?",
        document_ids=["doc-1"],
        session_id="sess-1",
        conversation_id="conv-1",
    )
    update = await tree_navigator_node(state)

    assert update == {"force_hybrid_fallback": True}
