"""Custom evaluation: 10 hand-crafted questions about the 3 seeded demo
documents (Tesla/NVIDIA/Apple 10-Ks), scored the same way as the FinanceBench
suite (same graph invocation, same LLM-as-judge) but against a curated set
instead of a random FinanceBench sample.

Stored under dataset="custom_demo", not "financebench" — these questions are
hand-picked against documents we know are ingested, which is a fundamentally
easier/different task than FinanceBench's random sample across its full
company universe (most of which isn't ingested locally). Keeping the dataset
label separate means GET /eval/summary's "Overall Accuracy" card — which
represents real FinanceBench performance — won't be inflated by this run.
GET /eval/history has no dataset filter, so this run's point still shows up
in the "Accuracy Over Time" chart.

CLI: python -m scripts.run_custom_eval
"""

import asyncio
from datetime import UTC, datetime
from statistics import mean

from sqlalchemy import select

from app.config import settings
from app.db.models import EvalRun, User
from app.db.session import AsyncSessionLocal
from app.eval.financebench_runner import FinanceBenchQuestion, _run_one_question
from app.logging import get_logger

log = get_logger(__name__)

_DEMO_USER_EMAIL = "demo@findoc.local"
_DATASET_NAME = "custom_demo"

# ticker/form_type/year match the exact filings already ingested by
# scripts/seed_sample_docs.py, so ensure_document_for_ticker finds the
# existing ready documents instead of re-fetching from SEC EDGAR.
_QUESTIONS: list[FinanceBenchQuestion] = [
    FinanceBenchQuestion(
        id="custom-01",
        question="What was Tesla's 2023 automotive gross margin?",
        gold_answer="19.4%",
        ticker="TSLA",
        form_type="10-K",
        year=2024,
    ),
    FinanceBenchQuestion(
        id="custom-02",
        question="What was Tesla's total revenue in 2023?",
        gold_answer="$96.77 billion (approximately $97 billion)",
        ticker="TSLA",
        form_type="10-K",
        year=2024,
    ),
    FinanceBenchQuestion(
        id="custom-03",
        question="What was NVIDIA's revenue in fiscal year 2024?",
        gold_answer="$60.9 billion",
        ticker="NVDA",
        form_type="10-K",
        year=2024,
    ),
    FinanceBenchQuestion(
        id="custom-04",
        question="How many employees did Apple have in 2023?",
        gold_answer="Approximately 161,000",
        ticker="AAPL",
        form_type="10-K",
        year=2023,
    ),
    FinanceBenchQuestion(
        id="custom-05",
        question="What was Apple's net income in fiscal 2023?",
        gold_answer="$96.995 billion",
        ticker="AAPL",
        form_type="10-K",
        year=2023,
    ),
    FinanceBenchQuestion(
        id="custom-06",
        question="What data center revenue did NVIDIA report in fiscal 2024?",
        gold_answer="$47.5 billion",
        ticker="NVDA",
        form_type="10-K",
        year=2024,
    ),
    FinanceBenchQuestion(
        id="custom-07",
        question="What was Tesla's net income in 2023?",
        gold_answer="$14.997 billion (approximately $15 billion)",
        ticker="TSLA",
        form_type="10-K",
        year=2024,
    ),
    FinanceBenchQuestion(
        id="custom-08",
        question="What was Apple's revenue in fiscal 2023?",
        gold_answer="$383.3 billion",
        ticker="AAPL",
        form_type="10-K",
        year=2023,
    ),
    FinanceBenchQuestion(
        id="custom-09",
        question="What were NVIDIA's main risk factors in fiscal 2024?",
        gold_answer="Supply chain constraints, competition, and export "
        "restrictions/geopolitical risk are among the main risk factors.",
        ticker="NVDA",
        form_type="10-K",
        year=2024,
    ),
    FinanceBenchQuestion(
        id="custom-10",
        question="What was Tesla's energy generation and storage revenue in 2023?",
        gold_answer="Approximately $6.04 billion",
        ticker="TSLA",
        form_type="10-K",
        year=2024,
    ),
]


async def _get_demo_user() -> User:
    async with AsyncSessionLocal() as db:
        user = (
            await db.execute(select(User).where(User.email == _DEMO_USER_EMAIL))
        ).scalar_one_or_none()
        if user is None:
            raise RuntimeError(
                f"{_DEMO_USER_EMAIL} not found — run "
                "`python -m scripts.create_demo_user` first."
            )
        return user


async def run_custom_eval() -> EvalRun:
    user = await _get_demo_user()

    question_results = []
    for i, q in enumerate(_QUESTIONS):
        log.info("custom_eval_question_start", index=i, total=len(_QUESTIONS), question_id=q.id)
        question_results.append(await _run_one_question(q, user.id))
        if i < len(_QUESTIONS) - 1:
            await asyncio.sleep(settings.EVAL_DELAY_SECS)

    scores = [r.score for r in question_results]
    overall_score = mean(scores) if scores else 0.0
    correct_count = sum(1 for r in question_results if r.correct)
    correct_pct = (correct_count / len(question_results) * 100) if question_results else 0.0

    now = datetime.now(UTC)
    async with AsyncSessionLocal() as db:
        eval_run = EvalRun(
            dataset=_DATASET_NAME,
            run_date=now,
            overall_score=overall_score,
            correct_pct=correct_pct,
            per_question_json=[
                {"question_id": r.question_id, "correct": r.correct, "score": r.score}
                for r in question_results
            ],
            model_version=f"{settings.GROQ_FAST_MODEL}/{settings.GROQ_CHAT_MODEL}",
            git_sha=None,
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


def main() -> None:
    eval_run = asyncio.run(run_custom_eval())
    print(
        f"EvalRun {eval_run.id} (dataset={eval_run.dataset}): "
        f"overall_score={eval_run.overall_score:.3f} correct_pct={eval_run.correct_pct:.1f}%"
    )


if __name__ == "__main__":
    main()
