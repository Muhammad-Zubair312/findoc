"""LangGraph node persisting the completed turn to Redis session memory. Always
the last node before END, regardless of which strategy answered the query."""

from typing import Any

from app.agent.state import FinDocState
from app.memory.session import append_session_turn


async def memory_writer_node(state: FinDocState) -> dict[str, Any]:
    await append_session_turn(state.session_id, state.query, state.answer)
    return {}
