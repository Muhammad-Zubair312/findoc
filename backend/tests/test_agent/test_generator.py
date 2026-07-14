"""generator_node: citation extraction from [N] markers, and the full node with
a stubbed LLM client."""

from typing import Any

import pytest

from app.agent.nodes.generator import _extract_citations, generator_node
from app.agent.state import FinDocState, Section


def _section(node_path: str, title: str) -> Section:
    return Section(
        node_path=node_path,
        title=title,
        full_text=f"Full text for {title}. " * 10,
        page_start=1,
        page_end=2,
        document_id="doc-1",
    )


class _FakeLLMClient:
    def __init__(self, content: str) -> None:
        self._content = content

    async def stream(self, **kwargs: Any) -> tuple[str, int, int, float]:
        on_token = kwargs.get("on_token")
        if on_token is not None:
            on_token(self._content)
        return self._content, 100, 50, 10.0


def test_extract_citations_maps_markers_to_sections() -> None:
    sections = [_section("s1", "Item 7"), _section("s2", "Item 8")]
    answer = "Revenue grew 10% [1]. Margin was 20% [2]. Both figures confirmed [1]."

    citations = _extract_citations(answer, sections)

    assert [c.index for c in citations] == [1, 2]
    assert citations[0].node_path == "s1"
    assert citations[1].node_path == "s2"


def test_extract_citations_ignores_out_of_range_markers() -> None:
    sections = [_section("s1", "Item 7")]
    answer = "Some claim [1]. An invalid one [5]."

    citations = _extract_citations(answer, sections)

    assert [c.index for c in citations] == [1]


def test_extract_citations_empty_when_no_markers() -> None:
    sections = [_section("s1", "Item 7")]
    assert _extract_citations("No citations here.", sections) == []


@pytest.mark.asyncio
async def test_generator_node_sets_answer_citations_and_tokens() -> None:
    sections = [_section("s1", "Item 7"), _section("s2", "Item 8")]
    fake_llm = _FakeLLMClient("Gross margin was 18.2% [1], up from prior year [2].")
    state = FinDocState(
        query="What was gross margin?",
        document_ids=["doc-1"],
        session_id="sess-1",
        conversation_id="conv-1",
        retrieved_sections=sections,
    )

    update = await generator_node(state, llm=fake_llm)  # type: ignore[arg-type]

    assert update["answer"] == "Gross margin was 18.2% [1], up from prior year [2]."
    assert [c.index for c in update["citations"]] == [1, 2]
    assert update["tokens_in"] == 100
    assert update["tokens_out"] == 50
