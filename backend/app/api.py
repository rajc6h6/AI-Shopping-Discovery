"""SSE streaming API endpoints for search and compare."""

import json
from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse
from app.models import SearchRequest, CompareRequest, OfflineRequest
from app.parser import parse_chat
from app.finder import find_products
from app.verifier import verify_match
from app.compare import compare_prices
from app.serpapi_client import SerpApiClient, CallCapExceeded, SerpApiError
from app.config import Settings

router = APIRouter(prefix="/api")


def _get_settings() -> Settings:
    return Settings()


@router.post("/search")
async def search(request: SearchRequest):
    """
    Main search endpoint: parse chat → find products → verify → stream results.
    Returns Server-Sent Events for progressive UI updates.
    """
    settings = _get_settings()

    async def event_generator():
        client = SerpApiClient(
            api_key=settings.serpapi_api_key,
            cache_db=settings.cache_db_path,
            max_calls=settings.max_calls_per_session,
            demo_mode=settings.demo_mode,
        )

        # --- Phase 1: Parse chat ---
        yield {
            "event": "trace",
            "data": json.dumps({
                "agent": "parser",
                "action": "Parsing chat to extract shoppable items",
                "engine": "Qwen2.5-72B (Featherless)",
                "status": "running",
            }),
        }

        try:
            parse_result = await parse_chat(
                request.chat_text,
                settings.featherless_api_key,
                request.audience,
            )
        except Exception as e:
            # Use the exception message directly — parser.py already produces clean messages
            yield {
                "event": "error",
                "data": json.dumps({"message": str(e)}),
            }
            return

        if not parse_result.items:
            yield {
                "event": "error",
                "data": json.dumps({
                    "message": "We couldn't find anything to shop for in that text — try describing what you're looking for.",
                }),
            }
            return

        yield {
            "event": "trace",
            "data": json.dumps({
                "agent": "parser",
                "action": f"Found {len(parse_result.items)} shoppable items",
                "engine": "Qwen2.5-72B (Featherless)",
                "status": "complete",
            }),
        }

        # Emit all parsed items
        for item in parse_result.items:
            yield {"event": "item_parsed", "data": item.model_dump_json()}

        # --- Phase 2: Find and verify products for each item ---
        for item in parse_result.items:
            yield {
                "event": "trace",
                "data": json.dumps({
                    "agent": "finder",
                    "action": f"Searching: {item.search_query}",
                    "engine": "Google Shopping",
                    "market": request.market,
                    "status": "running",
                }),
            }

            try:
                candidates = await find_products(item, client, request.market, request.audience)
            except CallCapExceeded:
                yield {
                    "event": "error",
                    "data": json.dumps({
                        "message": "SerpApi call limit reached for this session.",
                    }),
                }
                break
            except SerpApiError as e:
                yield {
                    "event": "trace",
                    "data": json.dumps({
                        "agent": "finder",
                        "action": f"Search failed: {str(e)}",
                        "engine": "Google Shopping",
                        "status": "error",
                    }),
                }
                candidates = []

            # Verify top 5 candidates
            verified = []
            for candidate in candidates[:5]:
                verification = verify_match(item, candidate, request.audience)
                verified.append({
                    "candidate": candidate.model_dump(),
                    "verification": verification.model_dump(),
                })

            # Sort by confidence descending
            verified.sort(
                key=lambda v: v["verification"]["overall_confidence"],
                reverse=True,
            )

            yield {
                "event": "trace",
                "data": json.dumps({
                    "agent": "finder",
                    "action": f"Found {len(verified)} verified results for '{item.category}'",
                    "engine": "Google Shopping",
                    "status": "complete",
                    "cached": any(
                        log.get("cached")
                        for log in client.get_call_log()
                        if log.get("engine") == "google_shopping"
                    ),
                }),
            }

            yield {
                "event": "product_found",
                "data": json.dumps({
                    "item": item.model_dump(),
                    "results": verified,
                }),
            }

        # --- Phase 3: Complete ---
        yield {
            "event": "complete",
            "data": json.dumps({
                "total_items": len(parse_result.items),
                "serpapi_calls": client.get_call_count(),
            }),
        }

    return EventSourceResponse(
        event_generator(),
        ping=15,
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/compare")
async def compare(request: CompareRequest):
    """
    Compare-prices endpoint: search multiple platforms for the same product.
    Returns SSE events for progressive compare results.
    """
    settings = _get_settings()

    async def event_generator():
        client = SerpApiClient(
            api_key=settings.serpapi_api_key,
            cache_db=settings.cache_db_path,
            max_calls=settings.max_calls_per_compare,
            demo_mode=settings.demo_mode,
        )

        yield {
            "event": "trace",
            "data": json.dumps({
                "agent": "compare-prices",
                "action": f"Comparing prices: {request.product_title[:60]}",
                "engine": "Multi-platform (Google Shopping, Amazon, eBay)",
                "status": "running",
            }),
        }

        try:
            result = await compare_prices(
                request.product_title,
                request.product_attributes,
                client,
                request.market,
                request.audience,
            )
        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"message": f"Compare failed: {str(e)}"}),
            }
            return

        yield {
            "event": "trace",
            "data": json.dumps({
                "agent": "compare-prices",
                "action": f"Found {len(result.offers)} offers across {len(result.search_engines_used)} platforms",
                "engine": ", ".join(result.search_engines_used),
                "status": "complete",
            }),
        }

        yield {
            "event": "compare_complete",
            "data": json.dumps(result.model_dump()),
        }

    return EventSourceResponse(
        event_generator(),
        ping=15,
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/offline")
async def offline_stores(request: OfflineRequest):
    """
    Offline mode: find physical stores of verified sellers near the user.
    Returns SSE events for progressive store discovery.
    """
    settings = _get_settings()

    if not settings.offline_mode:
        from starlette.responses import JSONResponse
        return JSONResponse(
            {"error": "Offline mode is disabled"},
            status_code=403,
        )

    async def event_generator():
        client = SerpApiClient(
            api_key=settings.serpapi_api_key,
            cache_db=settings.cache_db_path,
            max_calls=settings.max_calls_per_offline,
            demo_mode=settings.demo_mode,
        )

        yield {
            "event": "trace",
            "data": json.dumps({
                "agent": "offline",
                "action": (
                    f"Searching nearby stores for "
                    f"{'brands from online matches' if not request.is_specific and request.verified_results else str(len(request.sellers)) + ' sellers'}"
                ),
                "engine": "Google Maps",
                "audience": request.audience,
                "status": "running",
            }),
        }

        try:
            from app.store_finder import find_nearby_stores
            result = await find_nearby_stores(request, client)
        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"message": f"Offline search failed: {str(e)}"}),
            }
            return

        # Stream each store as it's found
        for store in result.stores:
            yield {
                "event": "store_found",
                "data": json.dumps(store.model_dump()),
            }

        yield {
            "event": "trace",
            "data": json.dumps({
                "agent": "offline",
                "action": f"Found {len(result.stores)} stores, {len(result.online_only_sellers)} sellers are online-only",
                "engine": "Google Maps",
                "status": "complete",
                "cached": any(
                    log.get("cached")
                    for log in client.get_call_log()
                ),
            }),
        }

        yield {
            "event": "offline_complete",
            "data": json.dumps({
                "stores": [s.model_dump() for s in result.stores],
                "online_only_sellers": result.online_only_sellers,
                "search_engines_used": result.search_engines_used,
                "serpapi_calls": client.get_call_count(),
                "empty_radius": result.empty_radius,
                "radius_km": result.radius_km,
                "brand_source_note": result.brand_source_note,
            }),
        }

    return EventSourceResponse(
        event_generator(),
        ping=15,
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
