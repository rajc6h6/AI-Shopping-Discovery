"""Tests for SerpApi response cache."""

import pytest
import tempfile
import os
from app.cache import SerpApiCache


class TestSerpApiCache:
    def test_cache_miss_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            cache = SerpApiCache(os.path.join(d, "test.db"))
            assert cache.get("nonexistent") is None
            cache.close()

    def test_cache_set_and_get(self):
        with tempfile.TemporaryDirectory() as d:
            cache = SerpApiCache(os.path.join(d, "test.db"))
            cache.set("key1", {"title": "Test Product", "price": 29.99})
            result = cache.get("key1")
            assert result == {"title": "Test Product", "price": 29.99}
            cache.close()

    def test_cache_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            cache = SerpApiCache(os.path.join(d, "test.db"))
            cache.set("key1", {"v": 1})
            cache.set("key1", {"v": 2})
            assert cache.get("key1") == {"v": 2}
            cache.close()

    def test_make_key_normalises_param_order(self):
        cache = SerpApiCache(":memory:")
        key1 = cache.make_key("google_shopping", {"q": "shoes", "gl": "in"})
        key2 = cache.make_key("google_shopping", {"gl": "in", "q": "shoes"})
        assert key1 == key2
        cache.close()

    def test_make_key_different_engines_differ(self):
        cache = SerpApiCache(":memory:")
        key1 = cache.make_key("google_shopping", {"q": "shoes"})
        key2 = cache.make_key("amazon", {"q": "shoes"})
        assert key1 != key2
        cache.close()

    def test_make_key_strips_api_key(self):
        cache = SerpApiCache(":memory:")
        key1 = cache.make_key("google_shopping", {"q": "shoes", "api_key": "secret1"})
        key2 = cache.make_key("google_shopping", {"q": "shoes", "api_key": "secret2"})
        assert key1 == key2
        cache.close()

    def test_count(self):
        cache = SerpApiCache(":memory:")
        assert cache.count() == 0
        cache.set("k1", {"a": 1})
        cache.set("k2", {"b": 2})
        assert cache.count() == 2
        cache.close()

    def test_persistence(self):
        with tempfile.TemporaryDirectory() as d:
            db_path = os.path.join(d, "persist.db")
            # Write
            cache1 = SerpApiCache(db_path)
            cache1.set("persist_key", {"data": "survives restart"})
            cache1.close()
            # Read in new instance
            cache2 = SerpApiCache(db_path)
            result = cache2.get("persist_key")
            assert result == {"data": "survives restart"}
            cache2.close()
