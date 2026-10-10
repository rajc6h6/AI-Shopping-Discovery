"""
Seed offline fixtures to cache for the demo to run without credits.
Usage: python scripts/seed_offline_fixtures.py
"""
import os
import sys
import asyncio
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
load_dotenv()

from app.models import OfflineRequest
from app.serpapi_client import SerpApiClient
from app.store_finder_v2 import find_nearby_stores_v2
from app.cache import BrandLogDB
from app.config import get_settings

async def seed_fixtures():
    settings = get_settings()
    if not settings.serpapi_api_key:
        print("Set SERPAPI_API_KEY in .env")
        return
        
    client = SerpApiClient(settings.serpapi_api_key, settings.cache_db_path, max_calls=200)
    brand_log = BrandLogDB(settings.cache_db_path)
    
    # Example 1: Formal Interview Chat (Navy Blazer) -> Peter England
    req1 = OfflineRequest(
        sellers=[],
        product_title="Navy Blazer",
        lat=19.0760, lng=72.8777, # Mumbai
        audience="male",
        is_specific=False,
        verified_results=[{
            "candidate": {"source": "Peter England", "title": "Peter England Men Navy Blue Solid Slim Fit Single-Breasted Blazer", "extracted_price": 3999.0},
            "verification": {"overall_confidence": 0.95, "scores": [], "label": "Exact"}
        }]
    )
    
    # Example 2: Casual Summer (Empty State)
    req2 = OfflineRequest(
        sellers=[],
        product_title="Summer Shorts",
        lat=19.0760, lng=72.8777,
        audience="male",
        is_specific=False,
        verified_results=[{
            "candidate": {"source": "FakeOnlineOnlyBrandXYZ", "title": "Summer Shorts", "extracted_price": 500.0},
            "verification": {"overall_confidence": 0.8, "scores": [], "label": "Variant"}
        }]
    )

    print("Seeding Mumbai - Peter England...")
    async for _ in find_nearby_stores_v2(req1, client, brand_log):
        pass
        
    print("Seeding Mumbai - Empty State...")
    async for _ in find_nearby_stores_v2(req2, client, brand_log):
        pass
        
    print("Seeding complete. Demo can now run entirely from cache.")

if __name__ == "__main__":
    asyncio.run(seed_fixtures())
