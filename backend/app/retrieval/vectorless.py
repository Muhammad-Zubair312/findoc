"""Vectorless RAG (PageIndex-style structural navigation) — the project's primary
retrieval strategy. GROQ_FAST_MODEL reads a compact outline of the document's tree
(titles + one-sentence summaries, never full_text) and picks which sections to
load in full, instead of a vector similarity search.
"""

import json
import uuid
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.state import Section
from app.config import settings
from app.db.models import Document, DocumentNode, DocumentTree
from app.db.session import AsyncSessionLocal
from app.llm.llm_client import LLMClient, llm_client
from app.llm.prompts import TREE_NAVIGATION_PROMPT, TREE_NAVIGATION_RETRY_SUFFIX
from app.logging import get_logger
from app.retrieval.types import RetrievalResult

log = get_logger(__name__)

_LARGE_TREE_NODE_THRESHOLD = 200
# Part=0, Item=1 — the stage-1 outline for large trees. NOT a depth-limiting
# size mitigation in the old sense: real SEC filings are wide (hundreds of
# same-depth subsections under a handful of Items), not deep, so cutting by
# depth alone barely reduces node count. This is genuinely two-stage
# navigation — stage 1 only ever sees Part/Item titles, then stage 2 gets the
# full subtree of just the branch(es) picked in stage 1.
_TOP_LEVEL_MAX_DEPTH = 1
# ~4 chars/token, budgeted well under Groq free tier's 6,000 TPM limit for
# GROQ_FAST_MODEL, leaving headroom for the surrounding prompt template text.
_SUBTREE_OUTLINE_CHAR_BUDGET = 18_000


class NavigationFailedError(Exception):
    pass


class _TreeNavigationResponse(BaseModel):
    reasoning: str
    selected_node_paths: list[str]


def _count_nodes(tree_json: dict[str, Any]) -> int:
    def count(node: dict[str, Any]) -> int:
        return 1 + sum(count(c) for c in node.get("children", []))

    root = tree_json.get("root", {})
    return sum(count(c) for c in root.get("children", []))


def _serialize_outline(
    tree_json: dict[str, Any], max_depth: int | None, include_summary: bool = True
) -> str:
    """Renders the tree as an indented outline: title (+ summary unless
    include_summary=False) per node, no full_text — the outline must fit
    comfortably in the fast model's context."""
    lines: list[str] = []

    def walk(node: dict[str, Any], depth: int) -> None:
        if max_depth is not None and depth > max_depth:
            return
        indent = "  " * depth
        if include_summary:
            summary = node.get("summary") or ""
            lines.append(f"{indent}- [{node['node_id']}] {node['title']}: {summary}")
        else:
            lines.append(f"{indent}- [{node['node_id']}] {node['title']}")
        for child in node.get("children", []):
            walk(child, depth + 1)

    root = tree_json.get("root", {})
    for child in root.get("children", []):
        walk(child, 0)

    return "\n".join(lines)


def _find_node(tree_json: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    def search(node: dict[str, Any]) -> dict[str, Any] | None:
        if node.get("node_id") == node_id:
            return node
        for child in node.get("children", []):
            found = search(child)
            if found is not None:
                return found
        return None

    for child in tree_json.get("root", {}).get("children", []):
        found = search(child)
        if found is not None:
            return found
    return None


def _serialize_subtree_outline(tree_json: dict[str, Any], node_ids: list[str]) -> str:
    """Full-depth outline of just the selected branch(es) (e.g. the Item(s)
    picked during stage-1 navigation) instead of the whole tree.

    A handful of Items are themselves too large for stage 2 even after
    narrowing (e.g. "Item 8. Financial Statements" can have 100s of
    footnote/line-item subsections, all at the same depth — no further depth
    cutoff would reduce that). If the full-detail render exceeds the budget,
    fall back to title-only lines (titles carry most of the signal; the
    summaries are what push it over) rather than risk another 413.
    """
    nodes = [n for n in (_find_node(tree_json, nid) for nid in node_ids) if n is not None]
    subtree = {"root": {"children": nodes}}

    outline = _serialize_outline(subtree, None)
    if len(outline) <= _SUBTREE_OUTLINE_CHAR_BUDGET:
        return outline

    log.warning(
        "vectorless_subtree_outline_truncated",
        char_count=len(outline),
        budget=_SUBTREE_OUTLINE_CHAR_BUDGET,
        node_ids=node_ids,
    )
    return _serialize_outline(subtree, None, include_summary=False)


class VectorlessRetriever:
    def __init__(self, llm: LLMClient = llm_client) -> None:
        self._llm = llm

    async def retrieve(self, query: str, document_id: str) -> RetrievalResult:
        async with AsyncSessionLocal() as db:
            tree = (
                await db.execute(
                    select(DocumentTree).where(DocumentTree.document_id == uuid.UUID(document_id))
                )
            ).scalar_one_or_none()
            if tree is None:
                raise NavigationFailedError(f"No tree found for document {document_id}")

            total_nodes = _count_nodes(tree.tree_json)

            if total_nodes > _LARGE_TREE_NODE_THRESHOLD:
                response = await self._navigate_large_tree(query, tree.tree_json)
            else:
                outline = _serialize_outline(tree.tree_json, None)
                response = await self._navigate(query, outline)
                if response is None:
                    raise NavigationFailedError("Model returned unparseable JSON twice")

            if not response.selected_node_paths:
                raise NavigationFailedError("Model selected no node paths")

            sections = await self._load_sections(db, document_id, response.selected_node_paths)
            if not sections:
                raise NavigationFailedError("All selected node paths were invalid")

            return RetrievalResult(
                sections=sections, reasoning=response.reasoning, strategy="vectorless"
            )

    async def _navigate_large_tree(
        self, query: str, tree_json: dict[str, Any]
    ) -> _TreeNavigationResponse:
        """Two-stage navigation: pick the relevant Part/Item branch(es) from a
        small top-level-only outline, then re-navigate within just those
        branches' full subtree. Keeps every individual LLM call's prompt
        bounded regardless of overall document size."""
        top_outline = _serialize_outline(tree_json, _TOP_LEVEL_MAX_DEPTH)
        top_response = await self._navigate(query, top_outline)
        if top_response is None:
            raise NavigationFailedError("Top-level navigation pass returned unparseable JSON twice")
        if not top_response.selected_node_paths:
            raise NavigationFailedError("Top-level navigation pass selected no branch")

        subtree_outline = _serialize_subtree_outline(tree_json, top_response.selected_node_paths)
        if not subtree_outline:
            return top_response

        detail_response = await self._navigate(query, subtree_outline)
        return detail_response if detail_response is not None else top_response

    async def _navigate(self, query: str, outline: str) -> _TreeNavigationResponse | None:
        prompt = TREE_NAVIGATION_PROMPT.format(tree_outline=outline, query=query)

        for attempt in range(2):
            content, _, _, _ = await self._llm.complete(
                model=settings.GROQ_FAST_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                response_format={"type": "json_object"},
                trace_name="tree_navigation",
            )
            try:
                data = json.loads(content)
                return _TreeNavigationResponse(**data)
            except (json.JSONDecodeError, ValidationError) as exc:
                log.warning("tree_navigation_invalid_json", attempt=attempt, error=str(exc))
                prompt = prompt + TREE_NAVIGATION_RETRY_SUFFIX

        return None

    async def _load_sections(
        self, db: AsyncSession, document_id: str, selected_paths: list[str]
    ) -> list[Section]:
        nodes = (
            (
                await db.execute(
                    select(DocumentNode).where(
                        DocumentNode.document_id == uuid.UUID(document_id),
                        DocumentNode.node_path.in_(selected_paths),
                    )
                )
            )
            .scalars()
            .all()
        )
        nodes_by_path = {n.node_path: n for n in nodes}

        document = (
            await db.execute(select(Document).where(Document.id == uuid.UUID(document_id)))
        ).scalar_one_or_none()
        document_name = (document.ticker or document.filename) if document is not None else document_id

        sections: list[Section] = []
        for path in selected_paths:
            node = nodes_by_path.get(path)
            if node is None:
                log.warning("tree_navigation_path_not_found", document_id=document_id, path=path)
                continue
            sections.append(
                Section(
                    node_path=node.node_path,
                    title=node.title,
                    full_text=node.full_text,
                    page_start=node.page_start,
                    page_end=node.page_end,
                    document_id=document_id,
                    document_name=document_name,
                )
            )
        return sections


vectorless_retriever = VectorlessRetriever()
