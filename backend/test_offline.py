
import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.models import OfflineRequest
from app.serpapi_client import SerpApiClient
from app.config import Settings
from app.store_finder_v2 import find_nearby_stores_v2
from app.cache import BrandLogDB

async def main():
    settings = Settings()
    client = SerpApiClient(
        api_key=settings.serpapi_api_key,
        cache_db=settings.cache_db_path,
        max_calls=10,
        demo_mode=False
    )
    brand_log = BrandLogDB(settings.cache_db_path)
    
    req = OfflineRequest(
        sellers=[{"name": "StockX"}],
        product_title="Nike Dunk Low Panda",
        lat=40.7128,
        lng=-74.0060,
        market="us",
        audience="male",
        is_specific=True,
        verified_results=[
            {
                "candidate": {
                    "title": "Nike Dunk Low Panda",
                    "source": "StockX"
                },
                "verification": {
                    "overall_confidence": 0.9
                }
            }
        ]
    )
    
    print("Testing offline store finder...")
    try:
        async for store, tier, why in find_nearby_stores_v2(req, client, brand_log):
            print(f"FOUND STORE: {store.title} ({tier}) - {why}")
    except Exception as e:
        print("ERROR:", str(e))
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())

