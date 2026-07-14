"""Eval endpoints: summary/history/failures/runs against directly-seeded EvalRun
rows (no live graph/judge calls needed for these — just the read-side API layer).
POST /eval/run is tested only for auth + response shape, not exercised live here
(that's covered by the CLI acceptance run of app.eval.financebench_runner)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.db.models import EvalQuestionResult, EvalRun
from app.db.session import AsyncSessionLocal

pytestmark = pytest.mark.asyncio


async def _register_and_login(client: AsyncClient) -> dict:
    email = f"user-{uuid.uuid4().hex[:12]}@example.com"
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "full_name": "Test User"},
    )
    assert resp.status_code == 201
    return resp.json()["user"]


async def _seed_eval_run(
    overall_score: float, correct_pct: float, run_date: datetime | None = None
) -> uuid.UUID:
    async with AsyncSessionLocal() as db:
        run = EvalRun(
            dataset="financebench",
            run_date=run_date or datetime.now(UTC),
            overall_score=overall_score,
            correct_pct=correct_pct,
            per_question_json=[],
            model_version="llama-3.1-8b-instant/llama-3.3-70b-versatile",
            completed_at=datetime.now(UTC),
        )
        db.add(run)
        await db.flush()

        db.add(
            EvalQuestionResult(
                run_id=run.id,
                question_id="q1",
                question_text="What was revenue?",
                predicted_answer="wrong answer",
                gold_answer="$1B",
                correct=False,
                score=0.2,
                strategy_used="hybrid",
                latency_ms=1200,
            )
        )
        db.add(
            EvalQuestionResult(
                run_id=run.id,
                question_id="q2",
                question_text="What was margin?",
                predicted_answer="18%",
                gold_answer="18%",
                correct=True,
                score=1.0,
                strategy_used="vectorless",
                latency_ms=800,
            )
        )
        await db.commit()
        return run.id


async def test_eval_summary_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/eval/summary")
    assert resp.status_code == 401


async def test_eval_summary_empty_when_no_runs(client: AsyncClient) -> None:
    await _register_and_login(client)
    resp = await client.get("/api/v1/eval/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["latest"] is None
    assert body["per_strategy_accuracy"] == {}


async def test_eval_summary_returns_latest_and_delta(client: AsyncClient) -> None:
    await _register_and_login(client)
    await _seed_eval_run(
        overall_score=0.5, correct_pct=50.0, run_date=datetime.now(UTC) - timedelta(days=1)
    )
    await _seed_eval_run(overall_score=0.7, correct_pct=70.0)

    resp = await client.get("/api/v1/eval/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["latest"]["overall_score"] == 0.7
    assert body["delta_overall_score"] == pytest.approx(0.2, abs=1e-6)
    assert body["delta_correct_pct"] == pytest.approx(20.0, abs=1e-6)
    assert body["per_strategy_accuracy"]["hybrid"] == 0.0
    assert body["per_strategy_accuracy"]["vectorless"] == 100.0


async def test_eval_history_filters_by_days(client: AsyncClient) -> None:
    await _register_and_login(client)
    await _seed_eval_run(0.5, 50.0, run_date=datetime.now(UTC) - timedelta(days=60))
    await _seed_eval_run(0.6, 60.0, run_date=datetime.now(UTC) - timedelta(days=1))

    resp = await client.get("/api/v1/eval/history?days=30")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["overall_score"] == 0.6


async def test_eval_failures_returns_incorrect_results_only(client: AsyncClient) -> None:
    await _register_and_login(client)
    await _seed_eval_run(0.6, 60.0)

    resp = await client.get("/api/v1/eval/failures?limit=10")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["question_id"] == "q1"


async def test_get_eval_run_not_found(client: AsyncClient) -> None:
    await _register_and_login(client)
    resp = await client.get(f"/api/v1/eval/runs/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_get_eval_run_returns_seeded_run(client: AsyncClient) -> None:
    await _register_and_login(client)
    run_id = await _seed_eval_run(0.8, 80.0)

    resp = await client.get(f"/api/v1/eval/runs/{run_id}")
    assert resp.status_code == 200
    assert resp.json()["overall_score"] == 0.8


async def test_trigger_eval_run_requires_auth(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/eval/run", json={})
    assert resp.status_code == 401


async def test_trigger_eval_run_enqueues_and_returns_task_id(client: AsyncClient) -> None:
    await _register_and_login(client)
    resp = await client.post("/api/v1/eval/run", json={"sample_size": 5})
    assert resp.status_code == 202
    assert "run_id" in resp.json()
