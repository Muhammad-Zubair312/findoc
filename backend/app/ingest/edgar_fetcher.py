"""SEC EDGAR API — resolve a ticker to a CIK, find a filing, download the primary document.

SEC requires a descriptive User-Agent on every request (see
https://www.sec.gov/os/webmaster-faq#developers) — requests without one get blocked.
"""

from datetime import date, datetime
from typing import Literal

import httpx
from pydantic import BaseModel

from app.config import settings

_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
_ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"

FilingType = Literal["10-K", "10-Q", "8-K"]


class EdgarFilingNotFoundError(Exception):
    pass


class FetchedFiling(BaseModel):
    ticker: str
    cik: str
    filer_name: str
    filing_type: str
    filing_date: date
    accession_number: str
    primary_document: str
    content: bytes
    content_type: str

    model_config = {"arbitrary_types_allowed": True}


async def _resolve_cik(client: httpx.AsyncClient, ticker: str) -> tuple[str, str]:
    """Returns (cik, company_name)."""
    resp = await client.get(_TICKER_MAP_URL)
    resp.raise_for_status()
    for entry in resp.json().values():
        if entry["ticker"].upper() == ticker.upper():
            return str(entry["cik_str"]), str(entry["title"])
    raise EdgarFilingNotFoundError(f"No CIK found for ticker '{ticker}'.")


async def fetch_filing(ticker: str, form_type: FilingType, year: int) -> FetchedFiling:
    """Finds the most recent filing of `form_type` filed in `year` for `ticker`,
    downloads its primary document, and returns it with metadata."""
    headers = {"User-Agent": settings.SEC_EDGAR_USER_AGENT}
    async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
        cik, company_name = await _resolve_cik(client, ticker)

        submissions_resp = await client.get(_SUBMISSIONS_URL.format(cik=int(cik)))
        submissions_resp.raise_for_status()
        recent = submissions_resp.json()["filings"]["recent"]

        match_index: int | None = None
        for i, form in enumerate(recent["form"]):
            if form != form_type:
                continue
            filing_date = datetime.strptime(recent["filingDate"][i], "%Y-%m-%d").date()
            if filing_date.year == year:
                match_index = i
                break

        if match_index is None:
            raise EdgarFilingNotFoundError(f"No {form_type} filing found for {ticker} in {year}.")

        accession_number = recent["accessionNumber"][match_index]
        primary_document = recent["primaryDocument"][match_index]
        filing_date = datetime.strptime(recent["filingDate"][match_index], "%Y-%m-%d").date()
        accession_no_dashes = accession_number.replace("-", "")

        doc_url = f"{_ARCHIVES_BASE}/{int(cik)}/{accession_no_dashes}/{primary_document}"
        doc_resp = await client.get(doc_url)
        doc_resp.raise_for_status()

        return FetchedFiling(
            ticker=ticker.upper(),
            cik=cik,
            filer_name=company_name,
            filing_type=form_type,
            filing_date=filing_date,
            accession_number=accession_number,
            primary_document=primary_document,
            content=doc_resp.content,
            content_type=doc_resp.headers.get("content-type", "text/html"),
        )
