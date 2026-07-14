"""The FinDoc Intelligence LangGraph: routes each query to Vectorless RAG,
hybrid retrieval, or direct knowledge, generates a cited answer, grades its
faithfulness, and retries (with a strategy flip) up to twice before persisting
the turn to session memory.

    START -> query_analyzer -> router
    router -> tree_navigator     (structural, 1 doc, confidence >= 0.7)
    router -> direct_llm         (direct, confidence >= 0.7)
    router -> hybrid_retriever   (everything else, including low confidence)
    tree_navigator -> hybrid_retriever   (if Vectorless RAG navigation failed)
    tree_navigator -> generator
    hybrid_retriever -> generator
    direct_llm -> generator
    generator -> grader
    grader -> memory_writer      (faithfulness >= 0.7, or MAX_RETRIES exhausted)
    grader -> router             (retry: grader_node set rewritten_query, strategy flips)
    memory_writer -> END
"""

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent.nodes.direct_llm import direct_llm_node
from app.agent.nodes.generator import generator_node
from app.agent.nodes.grader import FAITHFULNESS_THRESHOLD, grader_node
from app.agent.nodes.hybrid_retriever import hybrid_retriever_node
from app.agent.nodes.memory_writer import memory_writer_node
from app.agent.nodes.query_analyzer import query_analyzer_node
from app.agent.nodes.router import route_decision, router_node
from app.agent.nodes.tree_navigator import tree_navigator_node
from app.agent.state import FinDocState


def _tree_navigator_decision(state: FinDocState) -> str:
    return "hybrid_retriever" if state.force_hybrid_fallback else "generator"


def _grader_decision(state: FinDocState) -> str:
    if state.faithfulness_score is not None and state.faithfulness_score >= FAITHFULNESS_THRESHOLD:
        return "memory_writer"
    # grader_node is the sole authority on whether the MAX_RETRIES cap allows
    # another attempt — it explicitly sets rewritten_query to None when it
    # decides not to retry (see grader.py). Re-deriving that decision here
    # from retry_count alone is ambiguous: state.retry_count == MAX_RETRIES
    # means both "just used the last allowed retry, loop back" and "already
    # stopped in an earlier pass" and looks identical from this state alone.
    if state.rewritten_query is not None:
        return "router"
    return "memory_writer"


def build_graph() -> StateGraph[FinDocState]:
    graph = StateGraph(FinDocState)

    graph.add_node("query_analyzer", query_analyzer_node)
    graph.add_node("router", router_node)
    graph.add_node("tree_navigator", tree_navigator_node)
    graph.add_node("hybrid_retriever", hybrid_retriever_node)
    graph.add_node("direct_llm", direct_llm_node)
    graph.add_node("generator", generator_node)
    graph.add_node("grader", grader_node)
    graph.add_node("memory_writer", memory_writer_node)

    graph.add_edge(START, "query_analyzer")
    graph.add_edge("query_analyzer", "router")

    graph.add_conditional_edges(
        "router",
        route_decision,
        {
            "tree_navigator": "tree_navigator",
            "direct_llm": "direct_llm",
            "hybrid_retriever": "hybrid_retriever",
        },
    )

    graph.add_conditional_edges(
        "tree_navigator",
        _tree_navigator_decision,
        {"hybrid_retriever": "hybrid_retriever", "generator": "generator"},
    )

    graph.add_edge("hybrid_retriever", "generator")
    graph.add_edge("direct_llm", "generator")
    graph.add_edge("generator", "grader")

    graph.add_conditional_edges(
        "grader",
        _grader_decision,
        {"memory_writer": "memory_writer", "router": "router"},
    )

    graph.add_edge("memory_writer", END)

    return graph


_compiled_graph: CompiledStateGraph[FinDocState] | None = None


def get_graph() -> CompiledStateGraph[FinDocState]:
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph().compile()
    return _compiled_graph
