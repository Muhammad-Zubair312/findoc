"""CLI for manually exercising the graph end-to-end.

Usage:
    python -m app.agent.graph_cli --query "What was Tesla's 2023 gross margin?" \\
        --doc-id <document-id> [--doc-id <second-id> ...]
"""

import argparse
import asyncio
import uuid

from app.agent.graph import get_graph
from app.agent.state import FinDocState


async def _run(query: str, document_ids: list[str]) -> None:
    graph = get_graph()
    initial_state = FinDocState(
        query=query,
        document_ids=document_ids,
        session_id=str(uuid.uuid4()),
        conversation_id=str(uuid.uuid4()),
        # --doc-id is required (at least one), so document_ids is never empty
        # here and the router never falls back to resolving-by-user_id.
        user_id=str(uuid.uuid4()),
    )
    result = await graph.ainvoke(initial_state)

    print(f"\nStrategy used: {result.get('strategy_used')}")
    print(
        f"Query type: {result.get('query_type')} (confidence={result.get('classifier_confidence')})"
    )
    print(f"Retry count: {result.get('retry_count')}")
    print(f"Faithfulness score: {result.get('faithfulness_score')}")
    print(f"\nAnswer:\n{result.get('answer')}")
    print("\nCitations:")
    for citation in result.get("citations", []):
        print(f"  [{citation.index}] {citation.title} ({citation.node_path})")
    print(f"\nReasoning trace:\n{result.get('reasoning_trace')}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the FinDoc agent graph against a query.")
    parser.add_argument("--query", required=True, help="The user question.")
    parser.add_argument(
        "--doc-id",
        required=True,
        action="append",
        dest="doc_ids",
        help="Document UUID (repeatable).",
    )
    args = parser.parse_args()

    asyncio.run(_run(args.query, args.doc_ids))


if __name__ == "__main__":
    main()
