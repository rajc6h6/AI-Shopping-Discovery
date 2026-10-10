"""Tests for v2 offline store finder."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.store_finder_v2 import find_nearby_stores_v2, INDIAN_CHAINS
from app.models import OfflineRequest

pytestmark = pytest.mark.asyncio

def make_request(audience="male"):
    return OfflineRequest(
        sellers=[],
        product_title="Navy Blazer",
        lat=19.076, lng=72.878,
        market="in",
        audience=audience,
        is_specific=False,
        verified_results=[{
            "candidate": {"source": "Peter England", "title": "Peter England Blazer", "extracted_price": 3999.0},
            "verification": {"overall_confidence": 0.85, "scores": [], "label": "Best match"},
        }],
    )

def mock_client():
    client = MagicMock()
    client.search = AsyncMock(return_value={"local_results": []})
    client.get_call_count = MagicMock(return_value=0)
    return client

def mock_log():
    log = MagicMock()
    log.is_negative_cached = MagicMock(return_value=False)
    return log

async def test_category_sweep_uses_audience():
    client = mock_client()
    request = make_request("female")
    results = [item async for item in find_nearby_stores_v2(request, client, mock_log())]
    queries = [call.args[1]["q"] for call in client.search.call_args_list]
    assert any("women" in q.lower() for q in queries)

async def test_tier1_brand_stores_returned():
    place = {"title": "Peter England Exclusive", "types": ["clothing_store"],
             "gps_coordinates": {"latitude": 19.08, "longitude": 72.88},
             "place_id": "abc", "rating": 4.2}
    client = mock_client()
    # Mock search to return the place ONLY for the brand query
    async def mock_search(engine, params):
        if params["q"].startswith("Peter England"):
            return {"local_results": [place]}
        return {"local_results": []}
    client.search.side_effect = mock_search

    request = make_request()
    results = [item async for item in find_nearby_stores_v2(request, client, mock_log())]
    tiers = [r[1] for r in results]
    assert "tier1" in tiers

async def test_budget_not_exceeded():
    client = mock_client()
    client.search = AsyncMock(return_value={"local_results": []})
    request = make_request()
    
    # Track calls in our finder counter mock by providing a get_call_count that returns incrementing values
    # Actually store_finder_v2 uses internal counter for the loop, so just check call count at end
    async for _ in find_nearby_stores_v2(request, client, mock_log()):
        pass
    assert client.search.call_count <= 30

async def test_50km_enforced():
    far_place = {"title": "Peter England Store Pune", "types": ["clothing_store"],
                 "gps_coordinates": {"latitude": 18.52, "longitude": 73.86},  # ~150 km
                 "place_id": "far1"}
    client = mock_client()
    client.search = AsyncMock(return_value={"local_results": [far_place]})
    request = make_request()
    results = [item async for item in find_nearby_stores_v2(request, client, mock_log())]
    assert len(results) == 0

async def test_chain_is_tier2():
    place = {"title": "Lifestyle Stores", "types": ["clothing_store"],
             "gps_coordinates": {"latitude": 19.08, "longitude": 72.88},
             "place_id": "life"}
    client = mock_client()
    async def mock_search(engine, params):
        if params["q"] == "Lifestyle store":
            return {"local_results": [place]}
        return {"local_results": []}
    client.search.side_effect = mock_search

    request = make_request()
    results = [item async for item in find_nearby_stores_v2(request, client, mock_log())]
    # We should have one result, which is tier2
    assert len(results) == 1
    assert results[0][1] == "tier2"
