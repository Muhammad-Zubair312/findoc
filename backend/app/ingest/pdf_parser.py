"""Extracts an ordered, hierarchical list of sections from an ingested document.

Two source paths, sharing a common RawSection output:
  - parse_pdf(): generic uploaded PDFs, via pypdf + regex-based SEC-style heading
    detection (PART/Item patterns, falling back to generic heading heuristics).
  - parse_sec_html(): SEC EDGAR filings (always HTML), via sec-parser's native
    Part/Item semantic tree.

Note: `unstructured`'s PDF path (partition_pdf) is intentionally NOT used here. Its
layout-detection pipeline transitively imports torch via spacy/thinc even through
supposedly lightweight entry points, and on this machine that chain has produced a
hard segfault (not a catchable exception) when torch's native DLLs were in a bad
state. A segfault inside a Celery worker task is unrecoverable, so pypdf (pure
Python, no native inference deps) is used instead for the general PDF path.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import sec_parser as sp
from pypdf import PdfReader

_PART_RE = re.compile(r"^\s*PART\s+([IVXLC]+)\b", re.IGNORECASE)
_ITEM_RE = re.compile(r"^\s*Item\s+(\d+[A-Za-z]?)\.?\s*(.*)", re.IGNORECASE)
_GENERIC_HEADING_RE = re.compile(r"^[A-Z][A-Z0-9 ,.'&\-]{4,80}$")


@dataclass
class RawSection:
    title: str
    depth: int  # 0 = top-level (e.g. "PART I"), increasing = deeper
    text: str
    page_start: int | None
    page_end: int | None


def parse_pdf(file_path: Path) -> list[RawSection]:
    """Extracts sections from a generic PDF using page text + heading heuristics."""
    reader = PdfReader(str(file_path))
    sections: list[RawSection] = []
    current: RawSection | None = None

    for page_index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            depth = _classify_heading(line)
            if depth is not None:
                if current is not None:
                    sections.append(current)
                current = RawSection(
                    title=line[:300],
                    depth=depth,
                    text="",
                    page_start=page_index,
                    page_end=page_index,
                )
            else:
                if current is None:
                    current = RawSection(
                        title="Introduction",
                        depth=0,
                        text="",
                        page_start=page_index,
                        page_end=page_index,
                    )
                current.text += line + "\n"
                current.page_end = page_index

    if current is not None:
        sections.append(current)

    return sections


def _classify_heading(line: str) -> int | None:
    if _PART_RE.match(line):
        return 0
    if _ITEM_RE.match(line):
        return 1
    if _GENERIC_HEADING_RE.match(line) and len(line.split()) <= 12:
        return 2
    return None


def _classify_sec_depth(title: str) -> int:
    """sec-parser only ships Edgar10QParser (no 10-K-specific parser exists in
    this library, per sec-parser 0.58.1's public API) — used here for 10-Ks
    too since it's the only EDGAR HTML option, but its TreeBuilder nesting
    conflates a 10-K's PART/Item/subsection structure, misclassifying most
    10-K item numbers as "InvalidTopSectionIn10Q" and flattening what should
    be deep hierarchy (e.g. Item 1's subsections) into siblings at the same
    tree level. Overriding depth from the title text itself — using the same
    PART/Item regexes as the generic parse_pdf() path above — rebuilds the
    real Part > Item > Subsection hierarchy regardless of what level
    sec-parser's own tree put the node at."""
    if _PART_RE.match(title):
        return 0
    if _ITEM_RE.match(title):
        return 1
    return 2


def parse_sec_html(html: bytes) -> list[RawSection]:
    """Extracts sections from an SEC EDGAR filing using sec-parser's semantic tree."""
    elements = sp.Edgar10QParser().parse(html.decode("utf-8", errors="ignore"))
    tree = sp.TreeBuilder().build(elements)

    sections: list[RawSection] = []

    def walk(node: sp.TreeNode) -> None:
        element = node.semantic_element
        if isinstance(element, sp.TitleElement | sp.TopSectionTitle):
            title = (element.text or "Untitled section").strip()
            text = "\n".join(_collect_text(child) for child in node.children).strip()
            sections.append(
                RawSection(
                    title=title,
                    depth=_classify_sec_depth(title),
                    text=text,
                    page_start=None,
                    page_end=None,
                )
            )
        for child in node.children:
            walk(child)

    for root_node in tree.nodes:
        walk(root_node)

    return sections


def _collect_text(node: sp.TreeNode) -> str:
    element = node.semantic_element
    if isinstance(element, sp.TitleElement | sp.TopSectionTitle):
        return ""
    parts = [getattr(element, "text", "") or ""]
    for child in node.children:
        parts.append(_collect_text(child))
    return "\n".join(p for p in parts if p)
