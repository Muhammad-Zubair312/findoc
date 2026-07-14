"""route_decision() covers first-pass routing (query_type + confidence + doc
count) and retry-pass strategy flipping — pure function, no I/O."""

from app.agent.nodes.router import route_decision
from app.agent.state import FinDocState


def _state(**overrides: object) -> FinDocState:
    defaults: dict[str, object] = {
        "query": "q",
        "document_ids": ["doc-1"],
        "session_id": "s",
        "conversation_id": "c",
    }
    defaults.update(overrides)
    return FinDocState(**defaults)  # type: ignore[arg-type]


def test_structural_single_doc_high_confidence_goes_to_tree_navigator() -> None:
    state = _state(query_type="structural", classifier_confidence=0.9, document_ids=["doc-1"])
    assert route_decision(state) == "tree_navigator"


def test_structural_multi_doc_goes_to_hybrid_even_with_high_confidence() -> None:
    state = _state(
        query_type="structural", classifier_confidence=0.9, document_ids=["doc-1", "doc-2"]
    )
    assert route_decision(state) == "hybrid_retriever"


def test_structural_low_confidence_goes_to_hybrid() -> None:
    state = _state(query_type="structural", classifier_confidence=0.5, document_ids=["doc-1"])
    assert route_decision(state) == "hybrid_retriever"


def test_direct_high_confidence_goes_to_direct_llm() -> None:
    state = _state(query_type="direct", classifier_confidence=0.8)
    assert route_decision(state) == "direct_llm"


def test_direct_low_confidence_goes_to_hybrid() -> None:
    state = _state(query_type="direct", classifier_confidence=0.4)
    assert route_decision(state) == "hybrid_retriever"


def test_cross_doc_always_goes_to_hybrid() -> None:
    state = _state(query_type="cross_doc", classifier_confidence=0.95)
    assert route_decision(state) == "hybrid_retriever"


def test_keyword_always_goes_to_hybrid() -> None:
    state = _state(query_type="keyword", classifier_confidence=0.95)
    assert route_decision(state) == "hybrid_retriever"


def test_force_hybrid_fallback_overrides_structural_routing() -> None:
    state = _state(
        query_type="structural",
        classifier_confidence=0.99,
        document_ids=["doc-1"],
        force_hybrid_fallback=True,
    )
    assert route_decision(state) == "hybrid_retriever"


def test_retry_after_vectorless_forces_hybrid() -> None:
    state = _state(retry_count=1, strategy_used="vectorless", document_ids=["doc-1"])
    assert route_decision(state) == "hybrid_retriever"


def test_retry_after_hybrid_single_doc_tries_vectorless() -> None:
    state = _state(retry_count=1, strategy_used="hybrid", document_ids=["doc-1"])
    assert route_decision(state) == "tree_navigator"


def test_retry_after_hybrid_multi_doc_stays_hybrid() -> None:
    state = _state(retry_count=1, strategy_used="hybrid", document_ids=["doc-1", "doc-2"])
    assert route_decision(state) == "hybrid_retriever"


def test_retry_after_direct_stays_hybrid() -> None:
    state = _state(retry_count=1, strategy_used="direct", document_ids=["doc-1"])
    assert route_decision(state) == "hybrid_retriever"
