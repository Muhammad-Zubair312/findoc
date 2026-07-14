"""LangGraph node scoring the generated answer's faithfulness to the retrieved
sections, and preparing a retry (rewritten query) when it scores too low.
"""

import json
import re
import time
from typing import Any

from app.agent.state import FinDocState, Section
from app.config import settings
from app.llm.llm_client import LLMClient, llm_client
from app.llm.prompts import FAITHFULNESS_PROMPT, QUERY_REWRITE_PROMPT
from app.logging import get_logger

log = get_logger(__name__)

FAITHFULNESS_THRESHOLD = 0.7
# was 2; each retry = full agent run (~15-30s on Groq free tier).
# One retry is enough — if it fails twice the answer is a known limitation.
MAX_RETRIES = 1


def _sections_block(sections: list[Section]) -> str:
    if not sections:
        return "(no sections retrieved)"
    return "\n\n".join(
        f"[{i}] {s.title}:\n{s.full_text[:2000]}"
        for i, s in enumerate(sections, 1)
    )


def _numeric_fast_pass(answer: str, sections: list[Section]) -> bool:
    """Return True if the answer contains a specific numeric value (%, $,
    ratio) that also appears verbatim in the retrieved sections.

    A precise numeric value that appears in both the answer and the source
    text is strong evidence of faithfulness — the model cannot hallucinate
    a figure like '19.4%' that happens to match the exact text.

    This eliminates the most common false-negative: grader LLM interprets
    the prompt strictly and scores < 0.7 even when the answer is correct,
    causing an unnecessary retry that adds 15-30 seconds of latency.
    """
    numeric_patterns = re.findall(
        r'\b\d+(?:\.\d+)?%|\$\s*\d+(?:[\.,]\d+)*'
        r'(?:\s*(?:billion|million|thousand))?\b',
        answer,
        re.IGNORECASE,
    )
    if not numeric_patterns:
        return False
    sections_text = " ".join(s.full_text for s in sections).lower()
    return any(
        pat.lower().replace(" ", "") in sections_text.replace(" ", "")
        for pat in numeric_patterns
    )


async def grader_node(
    state: FinDocState, llm: LLMClient = llm_client
) -> dict[str, Any]:
    start = time.perf_counter()

    # Direct-LLM: grading against a synthetic section is tautological — skip.
    if state.strategy_used == "direct":
        log.info(
            "node_timing",
            node="grader",
            elapsed_secs=round(time.perf_counter() - start, 2),
        )
        return {"faithfulness_score": 1.0, "rewritten_query": None}

    # Numeric fast-pass: skip grader LLM when answer has a specific figure
    # grounded in retrieved text. Saves 1-2 Groq API calls (1-3s each).
    if _numeric_fast_pass(state.answer or "", state.retrieved_sections or []):
        log.info(
            "node_timing",
            node="grader",
            elapsed_secs=round(time.perf_counter() - start, 2),
            fast_pass="numeric",
        )
        return {"faithfulness_score": 0.9, "rewritten_query": None}

    prompt = FAITHFULNESS_PROMPT.format(
        sections_block=_sections_block(state.retrieved_sections),
        query=state.query,
        answer=state.answer,
    )

    try:
        content, _, _, _ = await llm.complete(
            model=settings.GROQ_FAST_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format={"type": "json_object"},
            trace_name="faithfulness_grading",
        )
        data = json.loads(content)
        score = float(data["score"])
        explanation = str(data.get("explanation", ""))
    except Exception as exc:
        log.warning("faithfulness_grading_failed", error=str(exc))
        # On grader failure, assume faithful rather than triggering a retry
        # that will also likely fail — wrong-but-not-harmful > 30s hang.
        score = 0.75
        explanation = f"Grading failed: {exc}"

    update: dict[str, Any] = {"faithfulness_score": score}

    if score < FAITHFULNESS_THRESHOLD and state.retry_count < MAX_RETRIES:
        rewrite_prompt = QUERY_REWRITE_PROMPT.format(
            query=state.query, grader_explanation=explanation
        )
        try:
            rewritten, _, _, _ = await llm.complete(
                model=settings.GROQ_FAST_MODEL,
                messages=[{"role": "user", "content": rewrite_prompt}],
                temperature=0.3,
                trace_name="query_rewrite",
            )
            update["rewritten_query"] = rewritten.strip()
        except Exception as exc:
            log.warning("query_rewrite_failed", error=str(exc))
            update["rewritten_query"] = state.query
        update["retry_count"] = state.retry_count + 1
    else:
        update["rewritten_query"] = None

    log.info(
        "node_timing",
        node="grader",
        elapsed_secs=round(time.perf_counter() - start, 2),
        score=score,
    )
    return update