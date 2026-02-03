from src.enrichment.context_writer import build_context_section
from src.enrichment.interfaces import SearchResult


def test_context_writer_stable_output():
    results = [
        SearchResult(
            url="https://example.com/a",
            title="Regulator announces investigation",
            snippet="The regulator opened an investigation into a financial scheme.",
            published_date="2026-01-01",
            source="Example",
        ),
        SearchResult(
            url="https://example.com/b",
            title="Court decision related to the case",
            snippet="A court decision mentioned the administrator and related entities.",
            published_date="2026-01-10",
            source="Example",
        ),
    ]
    context = build_context_section(results)
    assert context["available"] is True
    assert "verify" in context["overview"].lower()
    assert context["citations"][0]["url"] == "https://example.com/a"
    assert context["timeline"][0]["date"] == "2026-01-01"


def test_context_writer_empty_results():
    context = build_context_section([])
    assert context["available"] is False

