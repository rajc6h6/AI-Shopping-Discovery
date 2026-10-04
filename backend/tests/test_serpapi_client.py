"""Tests for SerpApi client."""

import pytest
import asyncio
from app.serpapi_client import SerpApiClient, CallCapExceeded


class TestSerpApiClient:
    def test_call_cap_raises_at_limit(self):
        client = SerpApiClient(api_key="fake", cache_db=":memory:", max_calls=2)
        client._call_count = 2
        with pytest.raises(CallCapExceeded):
            client._check_cap()

    def test_call_cap_ok_below_limit(self):
        client = SerpApiClient(api_key="fake", cache_db=":memory:", max_calls=10)
        client._call_count = 5
        client._check_cap()  # Should not raise

    def test_cached_result_returned_without_api_call(self):
        client = SerpApiClient(api_key="fake", cache_db=":memory:", max_calls=50)
        key = client.cache.make_key("google_shopping", {"q": "test"})
        client.cache.set(key, {"shopping_results": [{"title": "Cached Product"}]})

        result = asyncio.run(client.search("google_shopping", {"q": "test"}))
        assert result["shopping_results"][0]["title"] == "Cached Product"
        assert client.get_call_count() == 0  # No live call made

    def test_call_log_records_cache_hit(self):
        client = SerpApiClient(api_key="fake", cache_db=":memory:", max_calls=50)
        key = client.cache.make_key("amazon", {"search_term": "shoes"})
        client.cache.set(key, {"organic_results": []})

        asyncio.run(client.search("amazon", {"search_term": "shoes"}))
        log = client.get_call_log()
        assert len(log) == 1
        assert log[0]["cached"] is True
        assert log[0]["engine"] == "amazon"

    def test_initial_state(self):
        client = SerpApiClient(api_key="test", cache_db=":memory:", max_calls=50)
        assert client.get_call_count() == 0
        assert client.get_call_log() == []
