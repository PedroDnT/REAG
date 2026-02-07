from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class SearchResult:
    url: str
    title: str
    snippet: str
    published_date: str | None
    source: str | None = None


class ContextProvider(Protocol):
    def search(self, query: str, *, max_results: int, since_days: int) -> list[SearchResult]:
        raise NotImplementedError

    def fetch(self, urls: list[str]) -> list[dict[str, Any]]:
        """
        Best-effort content fetch.

        Implementations may return:
        - url
        - content_text
        - extracted_date
        """
        raise NotImplementedError

