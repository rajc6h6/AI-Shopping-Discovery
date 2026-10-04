"""Offline store finder: locates physical stores of verified online sellers nearby.

Uses SerpApi Google Maps engine to find stores, then filters with:
- Seller-to-store matching (for specific items with named sellers)
- Brand extraction + Maps search (for generic items)
- Strict 50 km radius enforcement using haversine distance
"""

import math
from app.models import StoreResult, OfflineRequest, OfflineResult
from app.serpapi_client import SerpApiClient
from app.store_matcher import match_store_to_seller
from app.brand_extractor import extract_brands_from_results

# ─── Constants ────────────────────────────────────────────────────────────────

# Single source of truth for the search radius — brief fixes this at 50 km.
# The frontend receives radius_km from the offline_complete event and draws
# the corresponding circle on the map.
OFFLINE_RADIUS_KM = 50

# Sellers known to be online-only (skip Maps search to save credits)
ONLINE_ONLY_SELLERS = {
    'amazon', 'flipkart', 'myntra', 'ajio', 'ebay', 'etsy',
    'meesho', 'snapdeal', 'shopclues', 'nykaa fashion',
    'shein', 'alibaba', 'aliexpress', 'wish', 'temu',
    'amazon india', 'amazon.in', 'amazon.com',
}

AUDIENCE_WORDS: dict[str, str] = {"male": "men", "female": "women"}


# ─── Pure helper functions ────────────────────────────────────────────────────

def _is_online_only(seller_name: str) -> bool:
    """Check if a seller is known to be online-only."""
    return seller_name.lower().strip() in ONLINE_ONLY_SELLERS


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate distance in km between two lat/lng points using the Haversine formula."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlng / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def _within_radius(
    user_lat: float, user_lng: float,
    store_lat: float, store_lng: float,
) -> bool:
    """Return True if the store is within OFFLINE_RADIUS_KM of the user."""
    return _haversine_km(user_lat, user_lng, store_lat, store_lng) <= OFFLINE_RADIUS_KM


def _build_maps_params(q: str, lat: float, lng: float) -> dict:
    """Build Google Maps search params. Location rounded to 2dp for cache-friendly keys."""
    return {
        "q": q,
        "ll": f"@{round(lat, 2)},{round(lng, 2)},14z",
        "type": "search",
        "hl": "en",
    }


def _build_seller_evidence(seller_name: str, price: str | None, platform: str | None) -> str:
    base = f"Part of {seller_name}"
    if price:
        return f"{base}, which lists this product online at {price}"
    if platform:
        return f"{base}, which sells this product on {platform}"
    return f"{base}, which lists this product online"


def _build_brand_evidence(brand: str, price: str | None) -> str:
    if price:
        return f"{brand} store. {brand} appears in your online matches at {price}."
    return f"{brand} store. {brand} appears in your online matches."


def _store_from_place(
    place: dict,
    seller_name: str,
    user_lat: float,
    user_lng: float,
    evidence_text: str,
    online_price: str | None,
    online_link: str | None,
    store_type: str | None = None,
) -> StoreResult | None:
    """
    Build a StoreResult from a Maps place dict.
    Returns None if the store has no coordinates or is outside the 50 km radius.
    """
    coords = place.get("gps_coordinates", {})
    store_lat = coords.get("latitude", 0)
    store_lng = coords.get("longitude", 0)

    # Exclude stores with no verifiable location
    if not (store_lat and store_lng):
        return None

    # Strict 50 km radius enforcement
    if not _within_radius(user_lat, user_lng, store_lat, store_lng):
        return None

    distance = _haversine_km(user_lat, user_lng, store_lat, store_lng)
    place_id = place.get("place_id", "")

    return StoreResult(
        title=place.get("title", seller_name),
        seller_name=seller_name,
        place_id=place_id,
        lat=store_lat,
        lng=store_lng,
        rating=place.get("rating"),
        reviews=place.get("reviews"),
        phone=place.get("phone"),
        website=place.get("website"),
        address=place.get("address"),
        thumbnail=place.get("thumbnail"),
        open_state=place.get("open_state") or place.get("hours"),
        hours=place.get("hours"),
        operating_hours=place.get("operating_hours"),
        store_type=store_type or place.get("type"),
        distance_km=round(distance, 1),
        evidence_text=evidence_text,
        online_price=online_price,
        online_link=online_link,
        maps_link=f"https://www.google.com/maps/place/?q=place_id:{place_id}",
    )


# ─── Seller-based path (specific items with named sellers) ───────────────────

async def _find_stores_by_sellers(
    request: OfflineRequest,
    client: SerpApiClient,
) -> OfflineResult:
    """
    For each verified seller, search Google Maps for nearby physical stores.
    Returns matched stores within 50 km and a list of online-only sellers.
    """
    stores: list[StoreResult] = []
    online_only: list[str] = []
    engines_used: list[str] = []

    for seller in request.sellers[:5]:  # Cap at 5 sellers to control budget
        seller_name = seller.get("name", "")
        if not seller_name:
            continue

        # Skip known online-only sellers
        if _is_online_only(seller_name):
            online_only.append(seller_name)
            continue

        # Search Google Maps
        q = f"{seller_name} store"
        params = _build_maps_params(q, request.lat, request.lng)

        try:
            data = await client.search("google_maps", params)
        except Exception:
            online_only.append(f"{seller_name} (search failed)")
            continue

        engines_used.append("google_maps")
        local_results = data.get("local_results", [])

        if not local_results:
            online_only.append(seller_name)
            continue

        matched_any = False
        for place in local_results[:5]:
            is_match, _reason = match_store_to_seller(place, seller_name)
            if not is_match:
                continue

            store = _store_from_place(
                place=place,
                seller_name=seller_name,
                user_lat=request.lat,
                user_lng=request.lng,
                evidence_text=_build_seller_evidence(
                    seller_name, seller.get("price"), seller.get("platform")
                ),
                online_price=seller.get("price"),
                online_link=seller.get("link"),
            )
            if store is not None:
                stores.append(store)
                matched_any = True

        if not matched_any:
            online_only.append(seller_name)

    _sort_stores(stores)

    return OfflineResult(
        stores=stores,
        online_only_sellers=online_only,
        search_engines_used=list(set(engines_used)),
        empty_radius=len(stores) == 0 and len(engines_used) > 0,
        radius_km=OFFLINE_RADIUS_KM,
    )


# ─── Brand-based path (generic items without a named brand) ──────────────────

async def _find_stores_by_brands(
    request: OfflineRequest,
    client: SerpApiClient,
    brands: list[str],
) -> OfflineResult:
    """
    For each extracted brand, search Google Maps for nearby stores.
    Returns stores within 50 km for matching brands.
    """
    audience_word = AUDIENCE_WORDS.get(request.audience, "")
    stores: list[StoreResult] = []
    engines_used: list[str] = []
    no_store_brands: list[str] = []

    for brand in brands:
        q = f"{brand} store"
        if audience_word:
            q += f" {audience_word}"
        params = _build_maps_params(q, request.lat, request.lng)

        try:
            data = await client.search("google_maps", params)
        except Exception:
            no_store_brands.append(f"{brand} (search failed)")
            continue

        engines_used.append("google_maps")
        local_results = data.get("local_results", [])

        found_in_radius = False
        for place in local_results[:5]:
            # Determine store type label from Maps title
            place_title = place.get("title", "")
            store_type = "Brand store" if brand.lower() in place_title.lower() else "Retailer"

            # Find a price from verified_results for the evidence line
            price_evidence: str | None = None
            for vr in request.verified_results:
                src = vr.get("candidate", {}).get("source", "")
                if brand.lower() in src.lower():
                    price_evidence = vr.get("candidate", {}).get("price")
                    break

            store = _store_from_place(
                place=place,
                seller_name=brand,
                user_lat=request.lat,
                user_lng=request.lng,
                evidence_text=_build_brand_evidence(brand, price_evidence),
                online_price=price_evidence,
                online_link=None,
                store_type=store_type,
            )
            if store is not None:
                stores.append(store)
                found_in_radius = True

        if not found_in_radius:
            no_store_brands.append(f"{brand} (no store within {OFFLINE_RADIUS_KM} km)")

    _sort_stores(stores)
    brand_note = f"Brands taken from your online matches: {', '.join(brands)}"

    return OfflineResult(
        stores=stores,
        online_only_sellers=no_store_brands,
        search_engines_used=list(set(engines_used)),
        empty_radius=len(stores) == 0 and len(engines_used) > 0,
        radius_km=OFFLINE_RADIUS_KM,
        brand_source_note=brand_note,
    )


# ─── Router ───────────────────────────────────────────────────────────────────

def _sort_stores(stores: list[StoreResult]) -> None:
    """Sort in-place: open stores first, then by distance ascending."""
    stores.sort(key=lambda s: (
        0 if s.open_state and 'open' in s.open_state.lower() else 1,
        s.distance_km or 999,
    ))


async def find_nearby_stores(
    request: OfflineRequest,
    client: SerpApiClient,
) -> OfflineResult:
    """
    Route to the appropriate store-search path:
    - Specific items (is_specific=True) or no verified_results → seller path
    - Generic items with verified_results → brand extraction path
    """
    if request.is_specific or not request.verified_results:
        return await _find_stores_by_sellers(request, client)

    # Generic item: extract brands from verified online results
    brands = extract_brands_from_results(request.verified_results, request.audience)

    if not brands:
        return OfflineResult(
            stores=[],
            online_only_sellers=["No brand could be identified from the online results"],
            search_engines_used=[],
            empty_radius=False,  # no search was attempted
            radius_km=OFFLINE_RADIUS_KM,
            brand_source_note=(
                "No brand could be identified from the online results — "
                "try searching for a specific brand."
            ),
        )

    return await _find_stores_by_brands(request, client, brands)
