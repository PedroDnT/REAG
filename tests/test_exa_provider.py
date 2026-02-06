"""Tests for the ExaProvider module."""

import pytest
from unittest.mock import patch, MagicMock
from src.enrichment.exa_provider import ExaProvider, ExaConfig
from src.enrichment.interfaces import SearchResult


@pytest.fixture
def provider():
    config = ExaConfig(api_key="test-key", base_url="https://api.exa.ai/search")
    return ExaProvider(config)


class TestExaProvider:
    def test_init(self, provider):
        assert provider.config.api_key == "test-key"
        assert provider.config.base_url == "https://api.exa.ai/search"
        assert provider.config.timeout_s == 30

    @patch("src.enrichment.exa_provider.os.getenv")
    def test_from_env_with_key(self, mock_getenv):
        mock_getenv.side_effect = lambda key, *args: {
            "EXA_API_KEY": "env-key",
            "EXA_BASE_URL": "https://example.com",
            "EXA_TIMEOUT_S": "10",
        }.get(key, args[0] if args else None)
        provider = ExaProvider.from_env()
        assert provider is not None
        assert provider.config.api_key == "env-key"

    @patch("src.enrichment.exa_provider.os.getenv", return_value=None)
    def test_from_env_without_key(self, mock_getenv):
        result = ExaProvider.from_env()
        assert result is None

    @patch("src.enrichment.exa_provider.requests.post")
    def test_search_parses_results(self, mock_post, provider):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {
                    "url": "https://example.com/article",
                    "title": "Test Article",
                    "text": "Snippet text here",
                    "publishedDate": "2024-01-01",
                    "source": "Example",
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        results = provider.search("test query", max_results=5, since_days=30)
        assert len(results) == 1
        assert isinstance(results[0], SearchResult)
        assert results[0].url == "https://example.com/article"
        assert results[0].title == "Test Article"

    @patch("src.enrichment.exa_provider.requests.post")
    def test_search_filters_empty_urls(self, mock_post, provider):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {"url": "", "title": "No URL", "text": "Snippet"},
                {"url": "https://valid.com", "title": "Valid", "text": "Text"},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        results = provider.search("query", max_results=5, since_days=30)
        assert len(results) == 1
        assert results[0].url == "https://valid.com"

    @patch("src.enrichment.exa_provider.requests.post")
    def test_search_empty_results(self, mock_post, provider):
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        results = provider.search("no results query", max_results=5, since_days=30)
        assert results == []

    @patch("src.enrichment.exa_provider.requests.post")
    def test_search_sends_correct_headers(self, mock_post, provider):
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        provider.search("query", max_results=10, since_days=7)

        call_kwargs = mock_post.call_args
        assert call_kwargs[1]["headers"]["x-api-key"] == "test-key"
        assert call_kwargs[1]["headers"]["content-type"] == "application/json"

    def test_fetch_returns_stubs(self, provider):
        urls = ["https://a.com", "https://b.com"]
        results = provider.fetch(urls)
        assert len(results) == 2
        assert results[0]["url"] == "https://a.com"
        assert results[0]["content_text"] == ""
        assert results[1]["url"] == "https://b.com"
