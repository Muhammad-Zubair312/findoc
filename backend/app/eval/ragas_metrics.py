"""Aggregate metrics over a completed FinanceBench run — not full RAGAS (which
would need additional context-precision/recall LLM calls not specified for this
project), just the aggregations GET /eval/summary needs, computed from data
already collected during the run (no extra LLM calls)."""

from collections import defaultdict

from app.db.models import EvalQuestionResult


def per_strategy_accuracy(results: list[EvalQuestionResult]) -> dict[str, float]:
    by_strategy: dict[str, list[bool]] = defaultdict(list)
    for r in results:
        by_strategy[r.strategy_used or "unknown"].append(r.correct)

    return {
        strategy: (sum(corrects) / len(corrects) * 100) if corrects else 0.0
        for strategy, corrects in by_strategy.items()
    }


def latency_percentiles(results: list[EvalQuestionResult]) -> dict[str, float | None]:
    latencies = sorted(r.latency_ms for r in results if r.latency_ms is not None)
    if not latencies:
        return {"p50": None, "p95": None}

    def percentile(data: list[int], pct: float) -> float:
        idx = min(int(len(data) * pct), len(data) - 1)
        return float(data[idx])

    return {"p50": percentile(latencies, 0.5), "p95": percentile(latencies, 0.95)}
