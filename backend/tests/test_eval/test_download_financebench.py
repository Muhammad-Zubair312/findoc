"""Company-name normalization/resolution — pure functions, no network needed."""

from scripts.download_financebench import _normalize_name, _resolve_ticker


def test_normalize_name_strips_common_suffixes() -> None:
    assert _normalize_name("3M Company") == "3m"
    assert _normalize_name("Kraft Heinz Co.") == "kraft heinz"
    assert _normalize_name("Apple Inc.") == "apple"
    assert _normalize_name("Amcor plc") == "amcor"


def test_normalize_name_strips_punctuation_and_collapses_whitespace() -> None:
    assert _normalize_name("AT&T,  Inc.") == "att"


def test_resolve_ticker_exact_match() -> None:
    index = {"3m": "MMM", "apple": "AAPL"}
    assert _resolve_ticker("3M", index) == "MMM"
    assert _resolve_ticker("Apple Inc.", index) == "AAPL"


def test_resolve_ticker_substring_fallback() -> None:
    index = {"amazoncom": "AMZN"}
    assert _resolve_ticker("Amazon", index) == "AMZN"


def test_resolve_ticker_returns_none_when_unresolvable() -> None:
    index = {"3m": "MMM"}
    assert _resolve_ticker("Totally Unknown Corp", index) is None
