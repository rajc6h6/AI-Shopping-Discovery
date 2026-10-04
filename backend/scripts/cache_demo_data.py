#!/usr/bin/env python3
"""
Pre-populate the SerpApi SQLite cache with demo data for all 3 scripted chats.

Run this ONCE with a real SERPAPI_API_KEY before setting DEMO_MODE=true.
After this script completes, the app works entirely from cache — no live API calls.

Usage:
    cd backend
    python scripts/cache_demo_data.py

Requires:
    - SERPAPI_API_KEY in .env or environment
    - pip install -r requirements.txt
"""

import asyncio
import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from app.config import Settings
from app.parser import parse_chat
from app.finder import find_products
from app.compare import compare_prices
from app.serpapi_client import SerpApiClient


DEMO_CHATS_DIR = Path(__file__).parent.parent / "demo_chats"


async def cache_demo_chat(chat_path: Path, settings: Settings) -> None:
    client = SerpApiClient(
        api_key=settings.serpapi_api_key,
        cache_db=settings.cache_db_path,
        max_calls=settings.max_calls_per_session,
    )

    chat_text = chat_path.read_text(encoding="utf-8")
    print(f"\n── {chat_path.stem} ──────────────────")

    print("  Parsing chat...")
    result = await parse_chat(
        chat_text,
        settings.bedrock_model_parse,
        settings.aws_bearer_token_bedrock,
        settings.aws_region,
    )
    print(f"  Found {len(result.items)} items")

    for item in result.items:
        print(f"  Searching: {item.search_query!r}...")
        candidates = await find_products(item, client, settings.default_market)
        print(f"    → {len(candidates)} results (calls so far: {client.get_call_count()})")

        # Also cache a compare run for the best candidate
        if candidates:
            top = candidates[0]
            attrs = {
                "category": item.category,
                "brand": item.brand or "",
                "model": item.model_name or "",
                "colour": item.colour or "",
                "material": item.material or "",
            }
            compare_client = SerpApiClient(
                api_key=settings.serpapi_api_key,
                cache_db=settings.cache_db_path,
                max_calls=settings.max_calls_per_compare,
            )
            print(f"  Comparing prices for: {top.title[:50]!r}...")
            await compare_prices(top.title, attrs, compare_client, settings.default_market)
            print(f"    → compare done (calls: {compare_client.get_call_count()})")

    print(f"  ✓ {chat_path.stem}: cache populated")


async def main():
    settings = Settings()

    if not settings.serpapi_api_key:
        print("ERROR: SERPAPI_API_KEY is not set. Set it in backend/.env")
        sys.exit(1)

    os.makedirs(os.path.dirname(settings.cache_db_path), exist_ok=True)

    chats = sorted(DEMO_CHATS_DIR.glob("*.txt"))
    if not chats:
        print(f"No demo chats found in {DEMO_CHATS_DIR}")
        sys.exit(1)

    print(f"Caching demo data for {len(chats)} chat(s)...")
    for chat_path in chats:
        await cache_demo_chat(chat_path, settings)

    print("\n✅ Done! Demo cache populated.")
    print("   Set DEMO_MODE=true in .env to serve from cache only.")


if __name__ == "__main__":
    asyncio.run(main())
