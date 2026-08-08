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


class TestCachedDecoratorArguments:
    """The cached() key used to ignore call arguments entirely.

    Every call through a decorated function collided on one cache entry, so the
    first result was returned for every subsequent input.
    """

    def test_different_positional_args_do_not_collide(self, tmp_path):
        cache = CacheManager(cache_dir=tmp_path)

        @cache.cached('square')
        def square(n):
            return n * n

        assert square(2) == 4
        assert square(5) == 25
        assert square(9) == 81

    def test_different_keyword_args_do_not_collide(self, tmp_path):
        cache = CacheManager(cache_dir=tmp_path)

        @cache.cached('add')
        def add(a, b=0):
            return a + b

        assert add(1, b=2) == 3
        assert add(1, b=9) == 10

    def test_repeated_call_is_served_from_cache(self, tmp_path):
        cache = CacheManager(cache_dir=tmp_path)
        calls = []

        @cache.cached('counted')
        def tracked(n):
            calls.append(n)
            return n * 10

        assert tracked(3) == 30
        assert tracked(3) == 30
        assert calls == [3], "second call should have been served from cache"

    def test_kwarg_order_does_not_change_the_key(self, tmp_path):
        cache = CacheManager(cache_dir=tmp_path)
        calls = []

        @cache.cached('kwargs')
        def combine(a=1, b=2):
            calls.append((a, b))
            return a * 100 + b

        assert combine(a=1, b=2) == 102
        assert combine(b=2, a=1) == 102
        assert len(calls) == 1

    def test_no_args_uses_the_base_key(self, tmp_path):
        cache = CacheManager(cache_dir=tmp_path)

        @cache.cached('constant')
        def value():
            return 42

        assert value() == 42
        assert cache.get('constant') == 42

    def test_decorator_preserves_function_metadata(self, tmp_path):
        cache = CacheManager(cache_dir=tmp_path)

        @cache.cached('documented')
        def documented(n):
            """Original docstring."""
            return n

        assert documented.__name__ == 'documented'
        assert documented.__doc__ == 'Original docstring.'
