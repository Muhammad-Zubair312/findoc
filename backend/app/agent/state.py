"""LangGraph state schema shared by every agent node (app/agent/nodes/*).

Field names deliberately avoid a leading underscore: LangGraph 1.x reconstructs a
fresh Pydantic instance per node call from its internal channel dict, and only
`model_fields` (public fields) round-trip through that reconstruction — a
leading-underscore attribute (a Pydantic *private* attribute, not a field) is
silently dropped between nodes and always resets to its default. Verified via a
minimal StateGraph repro before wiring the real graph (section 2.6); the fields
below that carry inter-node signals (`force_hybrid_fallback`, the classifier
confidence, token usage) are public for this reason.
"""

from typing import Literal

from pydantic import BaseModel


class Section(BaseModel):
    node_path: str
    title: str
    full_text: str
    page_start: int | None
    page_end: int | None
    document_id: str
    # Ticker (or filename fallback) — generator_node labels each section
    # with this in the prompt. Without it, cross-document queries only had
    # an opaque document_id UUID to go on, and the LLM was observed live
    # misattributing one company's figures to another when 3 companies'
    # sections ended up in the same prompt (e.g. "Apple's R&D is $X" where
    # $X was actually NVIDIA's figure — retrieval had the right content,
    # generation just couldn't tell which section belonged to which
    # company). Defaults to "" for direct_llm's synthetic section, where
    # there's no real document and no ambiguity to resolve.
    document_name: str = ""


class Citation(BaseModel):
    index: int  # [1], [2], [3] inline markers
    node_path: str
    title: str
    page_start: int | None
    page_end: int | None
    excerpt: str  # first 200 chars of full_text


class FinDocState(BaseModel):
    query: str
    query_type: Literal["structural", "cross_doc", "keyword", "direct"] | None = None
    document_ids: list[str]
    rewritten_query: str | None = None
    retrieved_sections: list[Section] = []
    reasoning_trace: str = ""
    answer: str = ""
    citations: list[Citation] = []
    faithfulness_score: float | None = None
    strategy_used: str | None = None
    retry_count: int = 0
    session_id: str
    conversation_id: str
    user_id: str
    # Set by tree_navigator_node on NavigationFailedError; read by the router to
    # send the query to hybrid_retriever instead. Public — see module docstring.
    force_hybrid_fallback: bool = False
    # Set by query_analyzer_node; read by the router alongside query_type.
    classifier_confidence: float | None = None
    # Set by generator_node from the LLM response's usage object; read by the
    # chat WS handler (section 2.7) when persisting the assistant Message.
    tokens_in: int | None = None
    tokens_out: int | None = None
