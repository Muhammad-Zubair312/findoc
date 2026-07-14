"""LangGraph node producing the final cited answer. Every path (tree_navigator,
hybrid_retriever, direct_llm) feeds into this node — it's the single place that
calls GROQ_CHAT_MODEL to turn retrieved_sections into prose with [N] citations.

Streams via LLMClient.stream(), pushing each token through LangGraph's custom
stream writer (get_stream_writer()) so a WS caller running the graph with
astream(stream_mode=["custom", "updates"]) gets real token-by-token output. The
writer is a verified no-op when there's no active stream consumer (e.g. the
plain graph.ainvoke() used by the CLI and the eval runner in 2.8), so this node
behaves identically for streaming and non-streaming callers — same return
contract, same final state, no divergent no-stream-mode code path.
"""

import re
import time
from typing import Any

from langgraph.config import get_stream_writer

from app.agent.state import Citation, FinDocState, Section
from app.config import settings
from app.llm.llm_client import LLMClient, llm_client
from app.llm.prompts import GENERATION_PROMPT
from app.logging import get_logger
from app.memory.session import get_session_memory

log = get_logger(__name__)

_CITATION_MARKER_RE = re.compile(r"\[(\d+)\]")
_MAX_SECTION_CHARS = 3000


def _build_sections_block(sections: list[Section]) -> str:
    if not sections:
        return "(no sections retrieved — answer from general knowledge only)"

    return "\n\n".join(
        f"[{i}] {s.title} (document: {s.document_name or s.document_id}, section {s.node_path}):\n"
        f"{s.full_text[:_MAX_SECTION_CHARS]}"
        for i, s in enumerate(sections, start=1)
    )


def _extract_citations(answer: str, sections: list[Section]) -> list[Citation]:
    indices = sorted({int(m) for m in _CITATION_MARKER_RE.findall(answer)})
    citations = []
    for idx in indices:
        if 1 <= idx <= len(sections):
            section = sections[idx - 1]
            citations.append(
                Citation(
                    index=idx,
                    node_path=section.node_path,
                    title=section.title,
                    page_start=section.page_start,
                    page_end=section.page_end,
                    excerpt=section.full_text[:200],
                )
            )
    return citations


async def generator_node(state: FinDocState, llm: LLMClient = llm_client) -> dict[str, Any]:
    """Returns: { answer, citations, tokens_in, tokens_out }."""
    start = time.perf_counter()
    session_memory = await get_session_memory(state.session_id)
    sections_block = _build_sections_block(state.retrieved_sections)

    prompt = GENERATION_PROMPT.format(
        session_memory=session_memory,
        sections_block=sections_block,
        query=state.rewritten_query or state.query,
    )

    try:
        writer = get_stream_writer()
    except RuntimeError:
        # No LangGraph runnable context at all (e.g. calling this node function
        # directly in a unit test, outside graph.ainvoke()/astream()) — verified
        # get_stream_writer() only no-ops for "no active stream consumer" inside
        # a real graph run; standalone calls raise instead. Fall back to a no-op.
        def writer(_: Any) -> None:
            return None

    def on_token(delta: str) -> None:
        writer({"type": "token", "content": delta})

    content, tokens_in, tokens_out, _ = await llm.stream(
        model=settings.GROQ_CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=1500,
        on_token=on_token,
        trace_name="generation",
    )

    citations = _extract_citations(content, state.retrieved_sections)

    log.info("node_timing", node="generator", elapsed_secs=round(time.perf_counter() - start, 2))
    return {
        "answer": content,
        "citations": citations,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
    }
