"""grader_node: threshold-driven retry decision, with a stubbed LLM client."""

import json
from typing import Any

import pytest

from app.agent.nodes.grader import grader_node
from app.agent.state import FinDocState

pytestmark = pytest.mark.asyncio


class _FakeLLMClient:
    """Returns a canned score on the grading call, then a canned rewrite on the
    (optional) rewrite call."""

    def __init__(self, score: float, rewritten_query: str = "rewritten question") -> None:
        self._score = score
        self._rewritten_query = rewritten_query
        self.calls: list[str] = []

    async def complete(self, **kwargs: Any) -> tuple[str, int, int, float]:
        trace_name = kwargs.get("trace_name", "")
        self.calls.append(trace_name)
        if trace_name == "faithfulness_grading":
            content = json.dumps({"score": self._score, "explanation": "test explanation"})
        else:
            content = self._rewritten_query
        return content, 10, 10, 5.0


def _state(**overrides: object) -> FinDocState:
    defaults: dict[str, object] = {
        "query": "What was revenue?",
        "document_ids": ["doc-1"],
        "session_id": "s",
        "conversation_id": "c",
        "answer": "Revenue was $1B [1].",
    }
    defaults.update(overrides)
    return FinDocState(**defaults)  # type: ignore[arg-type]


async def test_high_score_does_not_trigger_retry() -> None:
    fake_llm = _FakeLLMClient(score=0.9)
    update = await grader_node(_state(), llm=fake_llm)  # type: ignore[arg-type]

    assert update["faithfulness_score"] == 0.9
    assert "rewritten_query" not in update
    assert "retry_count" not in update
    assert fake_llm.calls == ["faithfulness_grading"]


async def test_low_score_under_retry_limit_triggers_rewrite() -> None:
    fake_llm = _FakeLLMClient(score=0.3, rewritten_query="What was Tesla's total revenue in 2023?")
    update = await grader_node(_state(retry_count=0), llm=fake_llm)  # type: ignore[arg-type]

    assert update["faithfulness_score"] == 0.3
    assert update["rewritten_query"] == "What was Tesla's total revenue in 2023?"
    assert update["retry_count"] == 1
    assert fake_llm.calls == ["faithfulness_grading", "query_rewrite"]


async def test_low_score_at_retry_limit_does_not_retry() -> None:
    fake_llm = _FakeLLMClient(score=0.2)
    update = await grader_node(_state(retry_count=2), llm=fake_llm)  # type: ignore[arg-type]

    assert update["faithfulness_score"] == 0.2
    assert "rewritten_query" not in update
    assert "retry_count" not in update
    assert fake_llm.calls == ["faithfulness_grading"]


async def test_grading_failure_defaults_to_zero_and_still_retries() -> None:
    class _BrokenLLMClient:
        async def complete(self, **kwargs: Any) -> tuple[str, int, int, float]:
            return "not json", 10, 10, 5.0

    update = await grader_node(_state(retry_count=0), llm=_BrokenLLMClient())  # type: ignore[arg-type]

    assert update["faithfulness_score"] == 0.0
    assert update["retry_count"] == 1
