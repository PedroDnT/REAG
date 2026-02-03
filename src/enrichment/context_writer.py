from __future__ import annotations

import re
from collections import Counter
from typing import Any

from .interfaces import SearchResult


_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "into",
    "onto",
    "over",
    "under",
    "are",
    "was",
    "were",
    "been",
    "being",
    "not",
    "but",
    "has",
    "have",
    "had",
    "its",
    "their",
    "they",
    "them",
    "you",
    "your",
    "about",
    "case",
    "report",
    "reports",
    "investigation",
    "alleged",
    "allegations",
}


def build_context_section(results: list[SearchResult]) -> dict[str, Any]:
    """
    Deterministic, non-LLM context section built from search result snippets.

    This is intentionally conservative: it avoids making definitive claims and
    frames information as "reported" when sourced from news/articles.
    """
    if not results:
        return {
            "available": False,
            "overview": "",
            "themes": [],
            "timeline": [],
            "citations": [],
        }

    citations = [
        {
            "url": r.url,
            "title": r.title,
            "published_date": r.published_date,
            "source": r.source,
        }
        for r in results
    ]

    overview = (
        "Context below was collected automatically from public sources and should be verified. "
        "It summarizes themes reported in the cited articles and does not constitute a factual determination."
    )

    themes = _extract_themes(results)
    timeline = _build_timeline(results)

    return {
        "available": True,
        "overview": overview,
        "themes": themes,
        "timeline": timeline,
        "citations": citations,
    }


def _extract_themes(results: list[SearchResult]) -> list[str]:
    text = " ".join([r.title + " " + r.snippet for r in results])
    tokens = [
        t.lower()
        for t in re.findall(r"[A-Za-z][A-Za-z\\-]{2,}", text)
        if t.lower() not in _STOPWORDS
    ]
    counts = Counter(tokens)
    top = [w for w, _ in counts.most_common(8)]
    return top


def _build_timeline(results: list[SearchResult]) -> list[dict[str, Any]]:
    dated = []
    for r in results:
        if r.published_date:
            dated.append((r.published_date, r.title, r.url))
    dated.sort()
    return [{"date": d, "title": t, "url": u} for d, t, u in dated[:6]]

