"""Tests for the CacheManager module."""

import pytest
import json
from datetime import timedelta
from pathlib import Path
from src.utils.caching import CacheManager


@pytest.fixture
def cache(tmp_path):
    return CacheManager(cache_dir=tmp_path / "cache")


class TestCacheManager:
    def test_init_creates_directory(self, tmp_path):
        cache_dir = tmp_path / "new_cache"
        CacheManager(cache_dir=cache_dir)
        assert cache_dir.exists()

    def test_set_and_get_json(self, cache):
        cache.set("test_key", {"value": 42})
        result = cache.get("test_key")
        assert result == {"value": 42}

    def test_get_nonexistent_returns_none(self, cache):
        assert cache.get("nonexistent") is None

    def test_set_and_get_string(self, cache):
        cache.set("str_key", "hello world")
        result = cache.get("str_key")
        assert result == "hello world"

    def test_set_and_get_list(self, cache):
        cache.set("list_key", [1, 2, 3])
        result = cache.get("list_key")
        assert result == [1, 2, 3]

    def test_set_and_get_pickle(self, cache):
        cache.set("pk", [1, 2, 3], format="pickle")
        result = cache.get("pk", format="pickle")
        assert result == [1, 2, 3]

    def test_max_age_expired(self, cache):
        cache.set("old", {"data": True})
        result = cache.get("old", max_age=timedelta(seconds=-1))
        assert result is None

    def test_max_age_fresh(self, cache):
        cache.set("fresh", {"data": True})
        result = cache.get("fresh", max_age=timedelta(hours=1))
        assert result == {"data": True}

    def test_clear_specific_key(self, cache):
        cache.set("keep", "a")
        cache.set("remove", "b")
        cache.clear("remove")
        assert cache.get("keep") == "a"
        assert cache.get("remove") is None

    def test_clear_all(self, cache):
        cache.set("k1", "v1")
        cache.set("k2", "v2")
        cache.clear()
        assert cache.get("k1") is None
        assert cache.get("k2") is None

    def test_overwrite_key(self, cache):
        cache.set("overwrite", {"v": 1})
        cache.set("overwrite", {"v": 2})
        assert cache.get("overwrite") == {"v": 2}

    def test_cached_decorator(self, cache):
        call_count = 0

        @cache.cached("decorator_key")
        def expensive_fn():
            nonlocal call_count
            call_count += 1
            return {"computed": True}

        result1 = expensive_fn()
        result2 = expensive_fn()
        assert result1 == {"computed": True}
        assert result2 == {"computed": True}
        assert call_count == 1

    def test_get_cache_info(self, cache):
        cache.set("info_test", "data")
        info = cache.get_cache_info()
        assert info["num_files"] >= 1
        assert info["total_size_mb"] >= 0

    def test_set_failure_does_not_raise(self, cache):
        """set() should not raise even if write fails."""
        cache.set("bad", lambda x: x, format="json")
        # Should not raise, just log warning

    def test_get_cache_path_deterministic(self, cache):
        """Same key should always map to the same path."""
        path1 = cache._get_cache_path("same_key")
        path2 = cache._get_cache_path("same_key")
        assert path1 == path2

    def test_different_keys_different_paths(self, cache):
        path1 = cache._get_cache_path("key_a")
        path2 = cache._get_cache_path("key_b")
        assert path1 != path2
