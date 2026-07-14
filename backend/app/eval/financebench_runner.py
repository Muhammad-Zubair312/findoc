"""Runs the FinanceBench eval suite: for each question, ensures the referenced
filing is ingested, runs the full agent graph, scores the answer with the LLM
judge, and persists an EvalRun + EvalQuestionResult per question.

CLI: python -m app.eval.financebench_runner --sample 10
Celery: run_financebench_task.delay(sample_size=10) (POST /eval/run)
"""

import argparse
import asyncio
import json
import secrets
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any

from openai import RateLimitError
from pydantic import BaseModel
from sqlalchemy import select

from app.agent.graph import get_graph
from app.agent.state import FinDocState
from app.config import settings
from app.db.models import EvalQuestionResult, EvalRun, User
from app.db.session import AsyncSessionLocal
from app.eval.judge import judge
from app.ingest.edgar_fetcher import FilingType
from app.ingest.pipeline import ensure_document_for_ticker
from app.logging import get_logger
from app.security.auth import hash_password
from app.workers.celery_app import celery_app

log = get_logger(__name__)

_QUESTIONS_PATH = Path(__file__).parent / "financebench_data" / "questions.json"
_EVAL_USER_EMAIL = "eval@findoc.local"
_RATE_LIMIT_BACKOFF_SECS = 60


class FinanceBenchQuestion(BaseModel):
    id: str
    question: str
    gold_answer: str
    ticker: str
    form_type: FilingType
    year: int


def _load_questions() -> list[FinanceBenchQuestion]:
    if not _QUESTIONS_PATH.exists():
        raise FileNotFoundError(
            f"{_QUESTIONS_PATH} not found — run `python -m scripts.download_financebench` first."
        )
    data = json.loads(_QUESTIONS_PATH.read_text(encoding="utf-8"))
    return [FinanceBenchQuestion(**q) for q in data["questions"]]


async def _get_or_create_eval_user() -> User:
    async with AsyncSessionLocal() as db:
        user = (
            await db.execute(select(User).where(User.email == _EVAL_USER_EMAIL))
        ).scalar_one_or_none()
        if user is not None:
            return user

        user = User(
            email=_EVAL_USER_EMAIL,
            hashed_password=hash_password(secrets.token_urlsafe(24)),
            full_name="Eval Runner",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


async def _run_one_question(
    question: FinanceBenchQuestion, user_id: uuid.UUID
) -> EvalQuestionResult:
    start = time.perf_counter()

    try:
        document = await ensure_document_for_ticker(
            user_id, question.ticker, question.form_type, question.year
        )
    except Exception as exc:
        log.warning(
            "financebench_ingest_failed",
            question_id=question.id,
            ticker=question.ticker,
            error=str(exc),
        )
        return EvalQuestionResult(
            question_id=question.id,
            question_text=question.question,
            predicted_answer="",
            gold_answer=question.gold_answer,
            correct=False,
            score=0.0,
            strategy_used=None,
            latency_ms=None,
            retrieved_sections_json={"error": f"ingestion failed: {exc}"},
        )

    state = FinDocState(
        query=question.question,
        document_ids=[str(document.id)],
        session_id=str(uuid.uuid4()),
        conversation_id=str(uuid.uuid4()),
        user_id=str(user_id),
    )

    graph = get_graph()
    result: dict[str, Any] = {}
    for attempt in range(2):
        try:
            result = await graph.ainvoke(state)
            break
        except RateLimitError:
            log.warning("financebench_rate_limited", question_id=question.id, attempt=attempt)
            await asyncio.sleep(_RATE_LIMIT_BACKOFF_SECS)

    predicted_answer = result.get("answer", "")
    judge_result = await judge.score(question.question, question.gold_answer, predicted_answer)
    latency_ms = (time.perf_counter() - start) * 1000

    sections = result.get("retrieved_sections", [])
    return EvalQuestionResult(
        question_id=question.id,
        question_text=question.question,
        predicted_answer=predicted_answer,
        gold_answer=question.gold_answer,
        correct=judge_result.correct,
        score=judge_result.score,
        strategy_used=result.get("strategy_used"),
        latency_ms=round(latency_ms),
        retrieved_sections_json=[s.model_dump() for s in sections] if sections else None,
    )


async def run_financebench(sample_size: int | None = None, git_sha: str | None = None) -> EvalRun:
    questions = _load_questions()
    if sample_size is not None:
        import random

        random.seed(42)
        questions = random.sample(questions, min(sample_size, len(questions)))

    user = await _get_or_create_eval_user()

    question_results: list[EvalQuestionResult] = []
    for i, q in enumerate(questions):
        log.info("financebench_question_start", index=i, total=len(questions), question_id=q.id)
        question_results.append(await _run_one_question(q, user.id))
        if i < len(questions) - 1:
            await asyncio.sleep(settings.EVAL_DELAY_SECS)

    scores = [r.score for r in question_results]
    overall_score = mean(scores) if scores else 0.0
    correct_count = sum(1 for r in question_results if r.correct)
    correct_pct = (correct_count / len(question_results) * 100) if question_results else 0.0

    now = datetime.now(UTC)
    async with AsyncSessionLocal() as db:
        eval_run = EvalRun(
            dataset="financebench",
            run_date=now,
            overall_score=overall_score,
            correct_pct=correct_pct,
            per_question_json=[
                {"question_id": r.question_id, "correct": r.correct, "score": r.score}
                for r in question_results
            ],
            model_version=f"{settings.GROQ_FAST_MODEL}/{settings.GROQ_CHAT_MODEL}",
            git_sha=git_sha,
            completed_at=now,
        )
        db.add(eval_run)
        await db.flush()

        for r in question_results:
            r.run_id = eval_run.id
            db.add(r)

        await db.commit()
        await db.refresh(eval_run)
        return eval_run


@celery_app.task(bind=True, time_limit=3600)
def run_financebench_task(
    self: object, sample_size: int | None = None, git_sha: str | None = None
) -> str:
    """Celery entry point for POST /eval/run. Wraps the whole run in one
    asyncio.run() call, same pattern as app.ingest.pipeline.ingest_document —
    one event loop for the entire task, relying on the async engine's
    pool_pre_ping=True to discard any stale connection from a previous task
    invocation in this worker process rather than reusing it across loops."""
    eval_run = asyncio.run(run_financebench(sample_size=sample_size, git_sha=git_sha))
    return str(eval_run.id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the FinanceBench eval suite.")
    parser.add_argument("--sample", type=int, default=None, help="Random sample size (seed=42).")
    parser.add_argument("--git-sha", type=str, default=None)
    args = parser.parse_args()

    eval_run = asyncio.run(run_financebench(sample_size=args.sample, git_sha=args.git_sha))
    print(
        f"EvalRun {eval_run.id}: overall_score={eval_run.overall_score:.3f} "
        f"correct_pct={eval_run.correct_pct:.1f}%"
    )


if __name__ == "__main__":
    main()
