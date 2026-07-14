"""LLM-as-judge for FinanceBench evaluation — scores a predicted answer against
the gold answer with semantic flexibility (paraphrasing, unit/formatting
differences allowed)."""

import json

from pydantic import BaseModel

from app.config import settings
from app.llm.llm_client import LLMClient, llm_client
from app.llm.prompts import JUDGE_PROMPT
from app.logging import get_logger

log = get_logger(__name__)


class JudgeResult(BaseModel):
    correct: bool
    score: float
    explanation: str


class Judge:
    def __init__(self, llm: LLMClient = llm_client) -> None:
        self._llm = llm

    async def score(self, question: str, gold_answer: str, predicted_answer: str) -> JudgeResult:
        prompt = JUDGE_PROMPT.format(
            question=question, gold_answer=gold_answer, predicted_answer=predicted_answer
        )
        try:
            content, _, _, _ = await self._llm.complete(
                model=settings.GROQ_CHAT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                response_format={"type": "json_object"},
                trace_name="eval_judge",
            )
            data = json.loads(content)
            return JudgeResult(
                correct=bool(data["correct"]),
                score=float(data["score"]),
                explanation=str(data.get("explanation", "")),
            )
        except Exception as exc:
            log.warning("judge_scoring_failed", error=str(exc))
            return JudgeResult(correct=False, score=0.0, explanation=f"Judge failed: {exc}")


judge = Judge()
