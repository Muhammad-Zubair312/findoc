"""Generates tests/fixtures/mini_10k.pdf (a synthetic 3-page filing with real
SEC heading patterns) before the e2e test runs, so it doesn't need to be
committed as a binary. pdf_parser.py's heading detection is pure regex over
extracted text (PART/Item patterns), so a reportlab-drawn PDF parses the same
as a real filing for ingestion purposes.
"""

from pathlib import Path

import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

_FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "mini_10k.pdf"

_LOREM = (
    "This section contains illustrative disclosure text used only to give the "
    "ingestion pipeline realistic paragraph content to chunk and summarize. It "
    "is not the real filing text and should not be relied upon for any purpose."
)


def _build_mini_10k(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=letter)
    width, height = letter

    def page(heading_lines: list[str]) -> None:
        y = height - 72
        for line in heading_lines:
            c.setFont("Helvetica-Bold", 13)
            c.drawString(72, y, line)
            y -= 20
            c.setFont("Helvetica", 10)
            for wrapped in (_LOREM[i : i + 90] for i in range(0, len(_LOREM), 90)):
                c.drawString(72, y, wrapped)
                y -= 14
            y -= 10
        c.showPage()

    page(["PART I", "Item 1. Business"])
    page(["Item 1A. Risk Factors"])
    page(["PART II", "Item 7. Management's Discussion and Analysis"])

    c.save()


@pytest.fixture(scope="session", autouse=True)
def _ensure_mini_10k_fixture() -> None:
    if not _FIXTURE_PATH.exists():
        _build_mini_10k(_FIXTURE_PATH)
