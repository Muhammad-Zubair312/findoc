"""Aggregate metrics computed purely from EvalQuestionResult objects — no DB, no
LLM needed."""

import pytest

from app.db.models import EvalQuestionResult
from app.eval.ragas_metrics import latency_percentiles, per_strategy_accuracy


def _result(
    strategy: str | None, correct: bool, latency_ms: int | None = None
) -> EvalQuestionResult:
    return EvalQuestionResult(
        question_id="q",
        question_text="q",
        predicted_answer="a",
        gold_answer="g",
        correct=correct,
        score=1.0 if correct else 0.0,
        strategy_used=strategy,
        latency_ms=latency_ms,
    )


def test_per_strategy_accuracy_computes_correctly() -> None:
    results = [
        _result("vectorless", True),
        _result("vectorless", True),
        _result("vectorless", False),
        _result("hybrid", False),
    ]

    accuracy = per_strategy_accuracy(results)

    assert accuracy["vectorless"] == pytest.approx(66.6667, abs=0.01)
    assert accuracy["hybrid"] == 0.0


def test_per_strategy_accuracy_groups_missing_strategy_as_unknown() -> None:
    results = [_result(None, True)]
    accuracy = per_strategy_accuracy(results)
    assert accuracy["unknown"] == 100.0


def test_per_strategy_accuracy_empty_list() -> None:
    assert per_strategy_accuracy([]) == {}


def test_latency_percentiles_computes_p50_p95() -> None:
    results = [_result("hybrid", True, latency_ms=ms) for ms in [100, 200, 300, 400, 500]]
    percentiles = latency_percentiles(results)
    assert percentiles["p50"] == 300.0
    assert percentiles["p95"] == 500.0


def test_latency_percentiles_empty_list() -> None:
    assert latency_percentiles([]) == {"p50": None, "p95": None}
