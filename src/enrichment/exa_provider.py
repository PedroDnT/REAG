from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests

from .interfaces import ContextProvider, SearchResult


@dataclass(frozen=True)
class ExaConfig:
    api_key: str
    base_url: str = "https://api.exa.ai/search"
    timeout_s: int = 30


class ExaProvider(ContextProvider):
    """
    Exa-based search provider.

    This implementation is intentionally minimal and is expected to be mocked in tests.
    """

    def __init__(self, config: ExaConfig):
        self.config = config

    @classmethod
    def from_env(cls) -> "ExaProvider | None":
        api_key = os.getenv("EXA_API_KEY")
        if not api_key:
            return None
        base_url = os.getenv("EXA_BASE_URL", "https://api.exa.ai/search")
        timeout_s = int(os.getenv("EXA_TIMEOUT_S", "30"))
        return cls(ExaConfig(api_key=api_key, base_url=base_url, timeout_s=timeout_s))

    def search(self, query: str, *, max_results: int, since_days: int) -> list[SearchResult]:
        headers = {"x-api-key": self.config.api_key, "content-type": "application/json"}
        payload: dict[str, Any] = {
            "query": query,
            "numResults": max_results,
            "useAutoprompt": True,
            "contents": {"text": True, "highlights": True},
            # Exa supports "startPublishedDate" but formats vary; keep since_days best-effort.
        }
        resp = requests.post(self.config.base_url, headers=headers, json=payload, timeout=self.config.timeout_s)
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data.get("results", []):
            results.append(
                SearchResult(
                    url=item.get("url", ""),
                    title=item.get("title", "") or "",
                    snippet=(item.get("text") or "")[:500],
                    published_date=item.get("publishedDate") or item.get("published_date"),
                    source=item.get("source"),
                )
            )
        return [r for r in results if r.url]

    def fetch(self, urls: list[str]) -> list[dict[str, Any]]:
        # Best-effort: we already get content in `search` (text/highlights). Return empty.
        return [{"url": u, "content_text": "", "extracted_date": None} for u in urls]

