import asyncio
from app.config import Settings
from app.serpapi_client import SerpApiClient

async def main():
    settings = Settings()
    print(f"SerpApi Key present: {bool(settings.serpapi_api_key)}")
    print(f"Key length: {len(settings.serpapi_api_key)}")
    
    client = SerpApiClient(
        api_key=settings.serpapi_api_key,
        cache_db=settings.cache_db_path,
        max_calls=10
    )
    
    params = {
        "q": "white converse sneakers",
        "gl": "us",
        "hl": "en",
        "num": 3
    }
    
    print("\nSending request to SerpApi (Google Shopping)...")
    try:
        data = await client.search("google_shopping", params)
        results = data.get("shopping_results", [])
        
        print(f"\nSUCCESS! Found {len(results)} shopping results.")
        for r in results[:3]:
            print(f"- {r.get('title')} | {r.get('price')} | {r.get('source')}")
            
    except Exception as e:
        print("\nERROR:")
        print(str(e))

if __name__ == "__main__":
    asyncio.run(main())
