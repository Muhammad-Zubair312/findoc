"""LangGraph node answering general financial-knowledge questions with no
document lookup (query_type="direct").

Wraps its answer as a single synthetic Section rather than setting state.answer
directly, so generator_node (which every path — tree_navigator, hybrid_retriever,
direct_llm — feeds into per the graph edges) stays the single place that produces
the final cited answer text.
"""

from typing import Any

from app.agent.state import FinDocState, Section
from app.config import settings
from app.llm.llm_client import LLMClient, llm_client
from app.llm.prompts import DIRECT_ANSWER_PROMPT

_DIRECT_KNOWLEDGE_NODE_PATH = "direct-knowledge"


async def direct_llm_node(state: FinDocState, llm: LLMClient = llm_client) -> dict[str, Any]:
    """Returns: { retrieved_sections, strategy_used }."""
    prompt = DIRECT_ANSWER_PROMPT.format(query=state.rewritten_query or state.query)

    content, _, _, _ = await llm.complete(
        model=settings.GROQ_FAST_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        trace_name="direct_answer",
    )

    section = Section(
        node_path=_DIRECT_KNOWLEDGE_NODE_PATH,
        title="General Knowledge",
        full_text=content,
        page_start=None,
        page_end=None,
        document_id="",
    )

    return {"retrieved_sections": [section], "strategy_used": "direct"}
