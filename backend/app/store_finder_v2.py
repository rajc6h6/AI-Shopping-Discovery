"""Offline store finder v2: 3-tier gated brand search."""
import math
from typing import AsyncIterator
from app.models import StoreResult, OfflineRequest
from app.serpapi_client import SerpApiClient
from app.brand_extractor import extract_brands_from_results
from app.store_matcher import match_store_to_brand, _is_clothing_type
from app.store_finder import OFFLINE_RADIUS_KM, _haversine_km, _within_radius, _build_maps_params
from app.cache import BrandLogDB

INDIAN_CHAINS = [
    "Lifestyle", "Westside", "Pantaloons", "Shoppers Stop",
    "Max Fashion", "Reliance Trends", "Central", "Brand Factory",
    "V-Mart", "FBB", "Zudio", "H&M", "Zara", "Uniqlo",
    "Marks & Spencer", "Levi's Store", "Allen Solly Studio",
    "Peter England", "Van Heusen", "Louis Philippe",
]

MAPS_CREDIT_BUDGET = 30

def _city_cell(lat: float, lng: float) -> str:
    """Cell key for negative cache roughly 10x10 km."""
    return f"{round(lat, 1)}_{round(lng, 1)}"

async def find_nearby_stores_v2(
    request: OfflineRequest,
    client: SerpApiClient,
    brand_log: BrandLogDB,
) -> AsyncIterator[tuple[StoreResult, str, str]]:
    """
    Yields (store, tier_label, why_shown) progressively.
    Enforces a strict credit budget and uses negative cache.
    """
    credits_used = 0
    cell = _city_cell(request.lat, request.lng)
    audience = request.audience.lower() if request.audience else "male"
    audience_word = "women's" if audience == "female" else "men's"
    seen_places = set()

    # Step 1: Extract Brands
    brands = []
    if request.is_specific:
        # For specific items, the search query is the most reliable source for the brand
        from app.brand_extractor import _extract_brand_from_title
        extracted = _extract_brand_from_title(request.product_title)
        if extracted:
            brands.append(extracted)

    if not brands and request.verified_results:
        brands = extract_brands_from_results(request.verified_results, request.audience)

    found_any_tier1 = False

    # Step 2: Brand queries (tier1)
    if brands:
        for brand in brands:
            if credits_used >= MAPS_CREDIT_BUDGET: break
            
            # Check negative cache
            if brand_log.is_negative_cached(brand, cell):
                continue
                
            q = f"{brand} store"
            params = _build_maps_params(q, request.lat, request.lng)
            try:
                data = await client.search("google_maps", params)
                credits_used += 1
            except Exception:
                continue

            found_brand = False
            for place in data.get("local_results", [])[:5]:
                coords = place.get("gps_coordinates", {})
                slat, slng = coords.get("latitude", 0), coords.get("longitude", 0)
                if not (slat and slng) or not _within_radius(request.lat, request.lng, slat, slng):
                    continue
                    
                place_id = place.get("place_id", "")
                if place_id in seen_places:
                    continue

                ok, _ = match_store_to_brand(place, brand)
                if ok:
                    seen_places.add(place_id)
                    found_brand = True
                    found_any_tier1 = True
                    dist = _haversine_km(request.lat, request.lng, slat, slng)
                    
                    brand_log.log_brand_search(brand, cell, "tier1", place_id, 1.0, slat, slng, True)
                    
                    store = StoreResult(
                        title=place.get("title", ""),
                        seller_name=brand,
                        place_id=place_id,
                        lat=slat, lng=slng,
                        rating=place.get("rating"),
                        reviews=place.get("reviews"),
                        phone=place.get("phone"),
                        website=place.get("website"),
                        address=place.get("address"),
                        thumbnail=place.get("thumbnail"),
                        open_state=place.get("open_state") or place.get("hours"),
                        hours=place.get("hours"),
                        operating_hours=place.get("operating_hours"),
                        store_type="Brand store",
                        distance_km=round(dist, 1),
                        evidence_text="",
                        maps_link=f"https://www.google.com/maps/place/?q=place_id:{place_id}",
                    )
                    yield store, "tier1", f"{brand} appears in your online matches"
            
            if not found_brand:
                brand_log.log_brand_search(brand, cell, "tier1", None, 0.0, 0.0, 0.0, False)

    # Step 3: Multi-brand Chains (tier2) fallback
    # If no tier 1 stores found, or if it's a generic item that might be stocked in multi-brand stores
    if not found_any_tier1 and credits_used < MAPS_CREDIT_BUDGET:
        if audience == "male":
            chain_q = "Lifestyle OR Shoppers Stop OR Pantaloons store men's clothing"
        elif audience == "female":
            chain_q = "Lifestyle OR Westside OR Pantaloons store women's clothing"
        else:
            chain_q = "Lifestyle OR Shoppers Stop OR Westside store clothing"
            
        params = _build_maps_params(chain_q, request.lat, request.lng)
        try:
            data = await client.search("google_maps", params)
            credits_used += 1
            for place in data.get("local_results", [])[:5]:
                coords = place.get("gps_coordinates", {})
                slat, slng = coords.get("latitude", 0), coords.get("longitude", 0)
                if not (slat and slng) or not _within_radius(request.lat, request.lng, slat, slng):
                    continue
                    
                place_id = place.get("place_id", "")
                if place_id in seen_places:
                    continue
                    
                place_title = place.get("title", "")
                is_indian_chain = any(c.lower() in place_title.lower() for c in INDIAN_CHAINS)
                
                # Looser match: either a known chain or a general clothing store
                if is_indian_chain or _is_clothing_type(place):
                    seen_places.add(place_id)
                    dist = _haversine_km(request.lat, request.lng, slat, slng)
                    
                    store = StoreResult(
                        title=place_title,
                        seller_name="Multi-brand retailer",
                        place_id=place_id,
                        lat=slat, lng=slng,
                        rating=place.get("rating"),
                        reviews=place.get("reviews"),
                        phone=place.get("phone"),
                        website=place.get("website"),
                        address=place.get("address"),
                        thumbnail=place.get("thumbnail"),
                        open_state=place.get("open_state") or place.get("hours"),
                        hours=place.get("hours"),
                        operating_hours=place.get("operating_hours"),
                        store_type="Multi-brand store" if is_indian_chain else "Retailer",
                        distance_km=round(dist, 1),
                        evidence_text="",
                        maps_link=f"https://www.google.com/maps/place/?q=place_id:{place_id}",
                    )
                    evidence = f"Likely carries {brands[0]} and similar brands" if brands else "Multi-brand store that carries this category"
                    yield store, "tier2", evidence
        except Exception:
            pass

    # Fallback for specific sellers
    if request.is_specific and not found_any_tier1:
        from app.store_finder import _find_stores_by_sellers
        res = await _find_stores_by_sellers(request, client)
        for store in res.stores:
            if store.place_id not in seen_places:
                seen_places.add(store.place_id)
                yield store, "tier1", store.evidence_text


