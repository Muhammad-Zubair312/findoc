"""FinanceBench evaluation endpoints."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EvalQuestionResult, EvalRun, User
from app.db.session import get_db
from app.eval.ragas_metrics import per_strategy_accuracy
from app.security.auth import get_current_user
from app.workers.tasks import run_financebench_task

router = APIRouter(prefix="/eval", tags=["eval"])


class EvalRunSummary(BaseModel):
    id: uuid.UUID
    dataset: str
    run_date: datetime
    overall_score: float
    correct_pct: float | None
    model_version: str
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class CustomBenchmarkSummary(BaseModel):
    overall_score: float
    run_date: datetime
    total_questions: int


class EvalSummaryResponse(BaseModel):
    latest: EvalRunSummary | None
    delta_overall_score: float | None
    delta_correct_pct: float | None
    per_strategy_accuracy: dict[str, float]
    total_questions: int
    p50_latency_ms: float | None
    # Always 0.0 — every LLM call goes through Groq's free tier
    # (app.llm.cost.calculate_cost returns 0.0 for every supported model).
    avg_cost_usd: float
    # Latest dataset="custom_demo" run (backend/scripts/run_custom_eval.py) —
    # kept separate from `latest`/the fields above, which are all scoped to
    # dataset="financebench", so the two benchmarks are never conflated.
    custom: CustomBenchmarkSummary | None


class EvalFailure(BaseModel):
    question_id: str
    question_text: str
    predicted_answer: str
    gold_answer: str
    score: float
    strategy_used: str | None
    latency_ms: int | None
    retrieved_sections_json: Any | None
    run_date: datetime

    model_config = {"from_attributes": True}


class RunEvalRequest(BaseModel):
    sample_size: int | None = None


class RunEvalResponse(BaseModel):
    run_id: str


async def _latest_custom_benchmark(db: AsyncSession) -> CustomBenchmarkSummary | None:
    run = (
        (
            await db.execute(
                select(EvalRun)
                .where(EvalRun.dataset == "custom_demo")
                .order_by(EvalRun.run_date.desc())
                .limit(1)
            )
        )
    ).scalar_one_or_none()
    if run is None:
        return None
    results = (
        await db.execute(select(EvalQuestionResult).where(EvalQuestionResult.run_id == run.id))
    ).scalars().all()
    return CustomBenchmarkSummary(
        overall_score=run.overall_score, run_date=run.run_date, total_questions=len(results)
    )


@router.get("/summary", response_model=EvalSummaryResponse)
async def eval_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EvalSummaryResponse:
    runs = (
        (
            await db.execute(
                select(EvalRun)
                .where(EvalRun.dataset == "financebench")
                .order_by(EvalRun.run_date.desc())
                .limit(2)
            )
        )
        .scalars()
        .all()
    )

    if not runs:
        return EvalSummaryResponse(
            latest=None,
            delta_overall_score=None,
            delta_correct_pct=None,
            per_strategy_accuracy={},
            total_questions=0,
            p50_latency_ms=None,
            avg_cost_usd=0.0,
            custom=await _latest_custom_benchmark(db),
        )

    latest = runs[0]
    previous = runs[1] if len(runs) > 1 else None

    results = (
        (await db.execute(select(EvalQuestionResult).where(EvalQuestionResult.run_id == latest.id)))
        .scalars()
        .all()
    )

    delta_correct_pct = None
    if previous is not None and latest.correct_pct is not None and previous.correct_pct is not None:
        delta_correct_pct = latest.correct_pct - previous.correct_pct

    latencies = sorted(r.latency_ms for r in results if r.latency_ms is not None)
    p50_latency_ms = float(latencies[len(latencies) // 2]) if latencies else None

    return EvalSummaryResponse(
        latest=EvalRunSummary.model_validate(latest),
        delta_overall_score=(latest.overall_score - previous.overall_score) if previous else None,
        delta_correct_pct=delta_correct_pct,
        total_questions=len(results),
        p50_latency_ms=p50_latency_ms,
        avg_cost_usd=0.0,
        per_strategy_accuracy=per_strategy_accuracy(list(results)),
        custom=await _latest_custom_benchmark(db),
    )


@router.get("/history", response_model=list[EvalRunSummary])
async def eval_history(
    days: int = 30,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[EvalRunSummary]:
    cutoff = datetime.now(UTC) - timedelta(days=days)
    runs = (
        (
            await db.execute(
                select(EvalRun).where(EvalRun.run_date >= cutoff).order_by(EvalRun.run_date.desc())
            )
        )
        .scalars()
        .all()
    )
    return [EvalRunSummary.model_validate(r) for r in runs]


@router.get("/failures", response_model=list[EvalFailure])
async def eval_failures(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[EvalFailure]:
    latest_run = (
        await db.execute(
            select(EvalRun)
            .where(EvalRun.dataset == "financebench")
            .order_by(EvalRun.run_date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if latest_run is None:
        return []

    results = (
        (
            await db.execute(
                select(EvalQuestionResult)
                .where(
                    EvalQuestionResult.run_id == latest_run.id,
                    EvalQuestionResult.correct.is_(False),
                )
                .order_by(EvalQuestionResult.score.asc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [
        EvalFailure(
            question_id=r.question_id,
            question_text=r.question_text,
            predicted_answer=r.predicted_answer,
            gold_answer=r.gold_answer,
            score=r.score,
            strategy_used=r.strategy_used,
            latency_ms=r.latency_ms,
            retrieved_sections_json=r.retrieved_sections_json,
            run_date=latest_run.run_date,
        )
        for r in results
    ]


@router.post("/run", response_model=RunEvalResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_eval_run(
    body: RunEvalRequest,
    current_user: User = Depends(get_current_user),
) -> RunEvalResponse:
    task = run_financebench_task.delay(sample_size=body.sample_size)
    return RunEvalResponse(run_id=task.id)


@router.get("/runs/{run_id}", response_model=EvalRunSummary)
async def get_eval_run(
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EvalRunSummary:
    run = await db.get(EvalRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Eval run not found.")
    return EvalRunSummary.model_validate(run)
