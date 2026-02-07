"""
Optional external context enrichment for flagged entities.

This package is designed to be provider-agnostic (Exa first; Perplexity later).
"""

from .interfaces import ContextProvider, SearchResult
from .context_writer import build_context_section

__all__ = [
    "ContextProvider",
    "SearchResult",
    "build_context_section",
]

