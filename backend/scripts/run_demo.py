import asyncio
import os
import sys

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.serpapi_client import SerpApiClient
from app.models import ParsedItem
from app.finder import find_products
from app.compare import compare_prices
from app.config import Settings

async def main():
    settings = Settings()
    client = SerpApiClient(
        api_key=settings.serpapi_api_key,
        cache_db=settings.cache_db_path,
        max_calls=100,
        demo_mode=False
    )
    
    products = [
        "Allen Edmonds Park Avenue shoes",
        "Nike Dunk Low Panda",
        "Carhartt WIP Michigan Chore Coat"
    ]
    
    for title in products:
        item = ParsedItem(
            category=title,
            is_specific=True,
            source_text=title,
            search_query=title,
            origin="stated"
        )
        print(f"\n--- Finding {title} ---")
        candidates = await find_products(item, client, "us", "male")
        if not candidates:
            print("No candidates found")
            continue
            
        cand = candidates[0]
        print(f"Top candidate: {cand.title}")
        print(f"Product ID: {cand.product_id}")
        print(f"Immersive Token: {cand.immersive_product_page_token}")
        
        print("Comparing prices...")
        async def trace(action, engine):
            print(f"TRACE: {action} ({engine})")
            
        res = await compare_prices(
            product_title=title,
            product_attributes={"category": title},
            client=client,
            market="us",
            audience="male",
            product_id=cand.product_id,
            immersive_product_page_token=cand.immersive_product_page_token,
            trace_callback=trace
        )
        print(f"Sellers found: {len(res.offers)}")
        print(f"Engines used: {res.search_engines_used}")
        for offer in res.offers[:3]:
            print(f" - {offer.seller}: {offer.price}")

if __name__ == "__main__":
    asyncio.run(main())
