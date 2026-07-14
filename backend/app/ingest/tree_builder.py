"""Builds a hierarchical document tree from parsed sections, summarizing each node
with GROQ_FAST_MODEL (cached in Redis) so the Vectorless RAG tree navigator (section
2.5) can browse the outline without reading full_text.

Runs inside the Celery ingestion task (app/ingest/pipeline.py), which wraps the
whole async pipeline in a single asyncio.run() — the `llm` client passed in here
must be an instance scoped to that one call (see pipeline.py), not the FastAPI
app's long-lived singleton, since httpx connections can't survive across separate
asyncio.run() event loops.
"""

import asyncio
import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import redis as sync_redis
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import DocumentNode, DocumentTree
from app.ingest.pdf_parser import RawSection
from app.llm.llm_client import LLMClient
from app.llm.prompts import TREE_NODE_SUMMARY_PROMPT
from app.logging import get_logger

log = get_logger(__name__)

_SUMMARY_CACHE_TTL_SECS = 7 * 24 * 3600
_redis_client = sync_redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


@dataclass
class _NodeAccumulator:
    node_id: str
    title: str
    text: str
    page_start: int | None
    page_end: int | None
    parent_path: str | None
    children: list["_NodeAccumulator"]
    summary: str = ""


def _cache_key(title: str, text: str) -> str:
    digest = hashlib.sha256(f"{title}{text[:500]}".encode()).hexdigest()
    return f"node_summary:{digest}"


async def _summarize_node(llm: LLMClient, title: str, text: str) -> str:
    key = _cache_key(title, text)
    cached = _redis_client.get(key)
    if cached:
        return str(cached)

    prompt = TREE_NODE_SUMMARY_PROMPT.format(title=title, text=text[:2000])
    content, _, _, _ = await llm.complete(
        model=settings.GROQ_FAST_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        trace_name="tree_node_summary",
    )
    summary = content.strip()
    _redis_client.setex(key, _SUMMARY_CACHE_TTL_SECS, summary)
    return summary


def _nest_sections(sections: list[RawSection]) -> list[_NodeAccumulator]:
    """Converts the flat, depth-annotated section list into a nested tree using a
    depth stack, and assigns sequential node_paths ("s1", "s1.1", "s1.2", "s2", ...)."""
    roots: list[_NodeAccumulator] = []
    stack: list[tuple[int, _NodeAccumulator]] = []  # (depth, node)
    counters: dict[str, int] = {}

    for section in sections:
        while stack and stack[-1][0] >= section.depth:
            stack.pop()

        parent = stack[-1][1] if stack else None
        parent_path = parent.node_id if parent else None
        counter_key = parent_path or "root"
        counters[counter_key] = counters.get(counter_key, 0) + 1
        node_id = (
            f"{parent_path}.{counters[counter_key]}" if parent_path else f"s{counters[counter_key]}"
        )

        node = _NodeAccumulator(
            node_id=node_id,
            title=section.title,
            text=section.text,
            page_start=section.page_start,
            page_end=section.page_end,
            parent_path=parent_path,
            children=[],
        )
        if parent is not None:
            parent.children.append(node)
        else:
            roots.append(node)
        stack.append((section.depth, node))

    return roots


def _merge_duplicate_siblings(nodes: list[_NodeAccumulator]) -> list[_NodeAccumulator]:
    """Merges sibling nodes sharing the same (whitespace/case-normalized)
    title into one, combining their children and keeping whichever has the
    longer text.

    SEC HTML filings sometimes yield the same logical Item as multiple
    separate structural elements from sec-parser's tree (observed live: a
    10-K's "Item 7" appeared 3 times, each a distinct top-level node) — left
    alone, this gives the LLM navigator several identically-titled but
    differently-populated node_ids to pick from, and it was observed to pick
    the wrong one (its own stated reasoning said "Item 7 or Item 8" but it
    selected an unrelated node). Merging can't lose information — it only
    ever unions text/children across nodes that render with an identical
    title — whereas keeping just one of several duplicates risks silently
    dropping real subsections attached to whichever copy wasn't kept.
    """
    merged: dict[str, _NodeAccumulator] = {}
    order: list[str] = []
    for node in nodes:
        key = " ".join(node.title.split()).strip().lower()
        if key not in merged:
            merged[key] = node
            order.append(key)
        else:
            existing = merged[key]
            if len(node.text) > len(existing.text):
                existing.text = node.text
            existing.children.extend(node.children)

    result = [merged[k] for k in order]
    for node in result:
        node.children = _merge_duplicate_siblings(node.children)
    return result


def _merge_duplicate_items_across_parts(roots: list[_NodeAccumulator]) -> list[_NodeAccumulator]:
    """Item numbers (e.g. "Item 7") are unique identifiers within a 10-K, but
    the same Item can end up nested under two different top-level PART
    containers rather than as true siblings (observed live: "Item 7" — which
    should only ever appear once, under PART II — also appeared as a child
    of a spurious extra "PART IV" alongside Items that don't belong there
    either, likely from a duplicated exhibit/XBRL-viewer copy of the
    filing's content). _merge_duplicate_siblings only merges duplicates that
    already share a parent, so this runs afterward to catch that case:
    same-titled Items are merged into the first-seen occurrence regardless
    of which PART contains them, and any PART left with zero children
    afterward (fully absorbed into another PART's copy) is dropped."""
    canonical_item: dict[str, _NodeAccumulator] = {}
    for part in roots:
        for item in part.children:
            key = " ".join(item.title.split()).strip().lower()
            if key not in canonical_item:
                canonical_item[key] = item
            else:
                existing = canonical_item[key]
                if len(item.text) > len(existing.text):
                    existing.text = item.text
                existing.children.extend(item.children)

    for part in roots:
        keep: list[_NodeAccumulator] = []
        for item in part.children:
            key = " ".join(item.title.split()).strip().lower()
            if canonical_item[key] is item:
                item.children = _merge_duplicate_siblings(item.children)
                keep.append(item)
        part.children = keep

    return [part for part in roots if part.children]


def _dedupe_verbatim_nodes(roots: list[_NodeAccumulator]) -> list[_NodeAccumulator]:
    """Final whole-tree pass: some subsections are duplicated verbatim under
    entirely unrelated parents elsewhere in the tree — not caught by
    _merge_duplicate_siblings (different parent) or
    _merge_duplicate_items_across_parts (different Item title, so not
    recognized as "the same Item"). Observed live: Apple's "Human Capital"
    subsection (260 chars of real text) appeared twice — once correctly
    under "Item 1. Business" and again under the unrelated "Item 1C.
    Cybersecurity" — confusing hybrid retrieval into surfacing the wrong
    parent's context.

    Only dedupes on an exact (title, non-empty text) match — deliberately
    does NOT key on empty text, since many legitimately distinct container
    nodes (e.g. two different "Overview" subsections under different Items)
    share a generic title with no text of their own; only an identical,
    non-trivial body of text is a safe signal of true duplication. Keeps
    the first occurrence in document order.
    """
    seen: set[tuple[str, str]] = set()

    def walk(nodes: list[_NodeAccumulator]) -> list[_NodeAccumulator]:
        result = []
        for node in nodes:
            text = node.text.strip()
            if text:
                key = (" ".join(node.title.split()).strip().lower(), text)
                if key in seen:
                    continue
                seen.add(key)
            node.children = walk(node.children)
            result.append(node)
        return result

    return walk(roots)


def _renumber(nodes: list[_NodeAccumulator], parent_path: str | None) -> None:
    """Re-assigns node_id/parent_path sequentially post-merge, since merging
    siblings changes how many nodes (and thus how many ids) exist at each
    level."""
    for i, node in enumerate(nodes, start=1):
        node.node_id = f"{parent_path}.{i}" if parent_path else f"s{i}"
        node.parent_path = parent_path
        _renumber(node.children, node.node_id)


async def build_tree(
    sections: list[RawSection], document_id: uuid.UUID, db: Session, llm: LLMClient
) -> DocumentTree:
    """Nests the flat section list, summarizes every node, and persists
    DocumentTree + DocumentNode rows. Returns the persisted DocumentTree."""
    roots = _nest_sections(sections)
    roots = _merge_duplicate_siblings(roots)
    roots = _merge_duplicate_items_across_parts(roots)
    roots = _dedupe_verbatim_nodes(roots)
    _renumber(roots, None)
    flat_nodes: list[_NodeAccumulator] = []

    def collect(node: _NodeAccumulator) -> None:
        flat_nodes.append(node)
        for child in node.children:
            collect(child)

    for root in roots:
        collect(root)

    for node in flat_nodes:
        node_text = node.text or node.title
        node.summary = await _summarize_node(llm, node.title, node_text)
        await asyncio.sleep(settings.INGEST_NODE_SUMMARY_DELAY_SECS)

    def to_json(node: _NodeAccumulator) -> dict[str, Any]:
        page_range = [node.page_start, node.page_end] if node.page_start is not None else None
        return {
            "node_id": node.node_id,
            "title": node.title,
            "summary": node.summary,
            "page_range": page_range,
            "children": [to_json(c) for c in node.children],
        }

    all_pages = [n.page_start for n in flat_nodes if n.page_start] + [
        n.page_end for n in flat_nodes if n.page_end
    ]
    tree_json = {
        "root": {
            "node_id": "root",
            "title": "Document Root",
            "summary": "",
            "page_range": [min(all_pages), max(all_pages)] if all_pages else None,
            "children": [to_json(r) for r in roots],
        }
    }

    tree = DocumentTree(
        document_id=document_id,
        tree_json=tree_json,
        node_count=len(flat_nodes),
        ingested_at=datetime.now(UTC),
    )
    db.add(tree)
    db.flush()

    for node in flat_nodes:
        db.add(
            DocumentNode(
                document_id=document_id,
                tree_id=tree.id,
                node_path=node.node_id,
                title=node.title,
                summary=node.summary,
                page_start=node.page_start,
                page_end=node.page_end,
                full_text=node.text or node.title,
                parent_path=node.parent_path,
            )
        )
    db.flush()

    return tree
