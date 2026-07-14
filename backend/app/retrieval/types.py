"""Shared result type produced by every retrieval strategy (vectorless, hybrid)."""

from typing import Literal

from pydantic import BaseModel

from app.agent.state import Section


class RetrievalResult(BaseModel):
    sections: list[Section]
    reasoning: str
    strategy: Literal["vectorless", "hybrid"]
