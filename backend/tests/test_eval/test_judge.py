"""Judge: JSON parsing of the LLM scoring response, with a stubbed LLM client."""

import json
from typing import Any

import pytest

from app.eval.judge import Judge

pytestmark = pytest.mark.asyncio


class _FakeLLMClient:
    def __init__(self, content: str) -> None:
        self._content = content

    async def complete(self, **kwargs: Any) -> tuple[str, int, int, float]:
        return self._content, 10, 10, 5.0


async def test_judge_parses_correct_response() -> None:
    fake_llm = _FakeLLMClient(
        json.dumps({"correct": True, "score": 0.95, "explanation": "Matches gold answer."})
    )
    judge = Judge(llm=fake_llm)  # type: ignore[arg-type]

    result = await judge.score("What was revenue?", "$1.5B", "Revenue was $1.5 billion.")

    assert result.correct is True
    assert result.score == 0.95
    assert result.explanation == "Matches gold answer."


async def test_judge_parses_incorrect_response() -> None:
    fake_llm = _FakeLLMClient(
        json.dumps({"correct": False, "score": 0.1, "explanation": "Wrong figure."})
    )
    judge = Judge(llm=fake_llm)  # type: ignore[arg-type]

    result = await judge.score("What was revenue?", "$1.5B", "Revenue was $2B.")

    assert result.correct is False
    assert result.score == 0.1


async def test_judge_defaults_to_incorrect_on_malformed_json() -> None:
    fake_llm = _FakeLLMClient("not valid json")
    judge = Judge(llm=fake_llm)  # type: ignore[arg-type]

    result = await judge.score("q", "gold", "predicted")

    assert result.correct is False
    assert result.score == 0.0
