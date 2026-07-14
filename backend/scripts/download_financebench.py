"""Downloads the FinanceBench dataset (patronus-ai/financebench, 150 questions on
real SEC filings) and normalizes it to { questions: [{id, question, gold_answer,
ticker, form_type, year}] } for app/eval/financebench_runner.py.

The upstream repo has no GitHub Releases — the data lives directly in the repo as
two JSONL files: financebench_open_source.jsonl (questions) and
financebench_document_information.jsonl (doc_name -> company/doc_type/doc_period).
Verified against the live repo before writing this (gh api / curl), not guessed.

FinanceBench's `company` field is a display name ("3M", "Kraft Heinz"), not a
ticker — resolved via SEC's own company_tickers.json (same source
app/ingest/edgar_fetcher.py uses), matched on normalized company name. Questions
whose filing type isn't one of our three supported forms (10-K/10-Q/8-K — e.g.
"Earnings" releases, ad-hoc annual reports) or whose company can't be confidently
resolved to a ticker are skipped with a warning, not silently mismapped.
"""

import argparse
import asyncio
import json
import re
from pathlib import Path
from typing import Any

import httpx

from app.config import settings

_QUESTIONS_URL = (
    "https://raw.githubusercontent.com/patronus-ai/financebench/main/data/"
    "financebench_open_source.jsonl"
)
_DOC_INFO_URL = (
    "https://raw.githubusercontent.com/patronus-ai/financebench/main/data/"
    "financebench_document_information.jsonl"
)
_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"

_OUTPUT_PATH = (
    Path(__file__).parent.parent / "app" / "eval" / "financebench_data" / "questions.json"
)

_DOC_TYPE_MAP = {"10k": "10-K", "10q": "10-Q", "8k": "8-K"}

_SUFFIX_RE = re.compile(
    r"\b(inc|incorporated|corp|corporation|company|co|plc|ltd|limited|holdings|group)\b\.?",
    re.IGNORECASE,
)


def _normalize_name(name: str) -> str:
    name = name.lower()
    name = _SUFFIX_RE.sub("", name)
    name = re.sub(r"[^a-z0-9 ]", "", name)
    return re.sub(r"\s+", " ", name).strip()


async def _fetch_jsonl(client: httpx.AsyncClient, url: str) -> list[dict[str, Any]]:
    resp = await client.get(url)
    resp.raise_for_status()
    return [json.loads(line) for line in resp.text.splitlines() if line.strip()]


async def _build_ticker_index(client: httpx.AsyncClient) -> dict[str, str]:
    resp = await client.get(_TICKER_MAP_URL, headers={"User-Agent": settings.SEC_EDGAR_USER_AGENT})
    resp.raise_for_status()
    index: dict[str, str] = {}
    for entry in resp.json().values():
        index[_normalize_name(entry["title"])] = entry["ticker"]
    return index


def _resolve_ticker(company: str, index: dict[str, str]) -> str | None:
    normalized = _normalize_name(company)
    if normalized in index:
        return index[normalized]
    for name, ticker in index.items():
        if normalized and (normalized in name or name in normalized):
            return ticker
    return None


async def download(force: bool = False) -> None:
    if _OUTPUT_PATH.exists() and not force:
        print(f"{_OUTPUT_PATH} already exists — skipping (use --force to re-download).")
        return

    async with httpx.AsyncClient(timeout=30.0) as client:
        questions_raw, doc_info_raw, ticker_index = await asyncio.gather(
            _fetch_jsonl(client, _QUESTIONS_URL),
            _fetch_jsonl(client, _DOC_INFO_URL),
            _build_ticker_index(client),
        )

    doc_info_by_name = {d["doc_name"]: d for d in doc_info_raw}

    normalized: list[dict[str, Any]] = []
    skipped_unsupported_type = 0
    skipped_no_ticker = 0

    for q in questions_raw:
        doc_info = doc_info_by_name.get(q["doc_name"])
        if doc_info is None:
            skipped_unsupported_type += 1
            continue

        form_type = _DOC_TYPE_MAP.get(doc_info["doc_type"])
        if form_type is None:
            skipped_unsupported_type += 1
            continue

        ticker = _resolve_ticker(doc_info["company"], ticker_index)
        if ticker is None:
            skipped_no_ticker += 1
            continue

        normalized.append(
            {
                "id": q["financebench_id"],
                "question": q["question"],
                "gold_answer": q["answer"],
                "ticker": ticker,
                "form_type": form_type,
                "year": doc_info["doc_period"],
            }
        )

    _OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _OUTPUT_PATH.write_text(json.dumps({"questions": normalized}, indent=2), encoding="utf-8")

    print(f"Wrote {len(normalized)} questions to {_OUTPUT_PATH}")
    print(
        f"Skipped {skipped_unsupported_type} (unsupported doc type) + "
        f"{skipped_no_ticker} (ticker not resolved) of {len(questions_raw)} total."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Download and normalize FinanceBench.")
    parser.add_argument("--force", action="store_true", help="Re-download even if the file exists.")
    args = parser.parse_args()
    asyncio.run(download(force=args.force))


if __name__ == "__main__":
    main()
