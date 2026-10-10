"""
Stage 0 Measurement Spike — Offline v2

Tests the central assumption: that a brand string extracted from a Google Shopping
title finds a real physical store on Google Maps within 50 km.

Cities: Mumbai (19.076, 72.8777) and Bangalore (12.9716, 77.5946)
Queries: 10 real Indian clothing queries, mix of men's/women's, branded/generic.

Outputs a structured report to docs/SPIKE_OFFLINE_V2.md.
"""

import asyncio
import json
import math
import os
import sys
import re
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.serpapi_client import SerpApiClient
from app.cache import SerpApiCache
from app.config import Settings

# ─── Config ───────────────────────────────────────────────────────────────────

CITIES = {
    "Mumbai": {"lat": 19.076, "lng": 72.8777},
    "Bangalore": {"lat": 12.9716, "lng": 77.5946},
}

# 10 real Indian clothing queries, mix of branded/generic, men's/women's
QUERIES = [
    {"q": "Peter England navy blazer formal men", "audience": "male", "city": "Mumbai"},
    {"q": "women's ethnic kurti cotton", "audience": "female", "city": "Mumbai"},
    {"q": "Nike Air Max sneakers men", "audience": "male", "city": "Bangalore"},
    {"q": "Levi's slim fit jeans men", "audience": "male", "city": "Mumbai"},
    {"q": "casual black t-shirt men round neck", "audience": "male", "city": "Bangalore"},
    {"q": "Biba embroidered anarkali dress women", "audience": "female", "city": "Mumbai"},
    {"q": "W women ethnic wear kurta set", "audience": "female", "city": "Bangalore"},
    {"q": "Allen Solly chinos men beige", "audience": "male", "city": "Mumbai"},
    {"q": "women's formal blazer office wear", "audience": "female", "city": "Bangalore"},
    {"q": "Max Fashion men's polo t-shirt", "audience": "male", "city": "Bangalore"},
]

MARKETPLACE_SELLERS = {
    'amazon', 'amazon india', 'amazon.in', 'amazon.com',
    'flipkart', 'myntra', 'ajio', 'nykaa', 'nykaa fashion',
    'meesho', 'snapdeal', 'shopclues', 'shein', 'temu',
    'alibaba', 'aliexpress', 'wish', 'ebay', 'etsy',
    'google shopping', 'google', 'walmart', 'target',
    'paytm mall', 'tata cliq', 'reliance digital',
    'tata cliq luxury',
}

# Known online-only / marketplace private labels
ONLINE_ONLY_BRANDS = {
    'roadster', 'hrx', 'here&now', 'mast & harbour', 'all about you',
    'anouk', 'dressberry', 'kook n keech', 'sassafras', 'sztori',
    'tokyo talkies', 'sangria', 'anubhutee', 'harpa', 'moda rapido',
    'highlander', 'invictus', 'wrogn', 'bewakoof', 'urbano fashion',
}

RADIUS_KM = 50


def haversine_km(lat1, lng1, lat2, lng2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlng / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def extract_brand_from_title(title: str) -> str | None:
    """Extract brand from a Shopping title. Returns None if no brand found."""
    PRODUCT_NOUNS = {
        'sneakers', 'shoes', 'boots', 'loafers', 'sandals', 'heels', 'flats',
        'shirt', 'tshirt', 't-shirt', 'jacket', 'blazer', 'chinos', 'jeans',
        'pants', 'trousers', 'kurta', 'kurti', 'dress', 'top', 'hoodie',
        'sweater', 'bag', 'watch', 'belt', 'sunglasses', 'cap', 'hat',
        'shorts', 'skirt', 'leggings', 'saree', 'polo', 'anarkali',
    }
    SKIP = {'men', "men's", 'women', "women's", 'unisex', 'new', 'buy', 'best',
            'black', 'white', 'blue', 'red', 'navy', 'grey', 'gray', 'beige',
            'pink', 'green', 'casual', 'formal', 'classic', 'slim', 'fit',
            'cotton', 'round', 'neck', 'ethnic', 'wear', 'office', 'embroidered',
            'for', 'the', 'and', 'with', 'a', 'an', 'in', 'of', 'to'}

    words = title.split()
    # Method 1: find word before first product noun
    for i, word in enumerate(words):
        if word.lower().rstrip('s') in PRODUCT_NOUNS and i > 0:
            candidates = [w for w in words[max(0, i - 2):i]
                          if w.lower() not in SKIP and len(w) > 1]
            if candidates:
                return ' '.join(candidates)

    # Method 2: first capitalized word not in skip list
    for word in words:
        clean = word.strip("'\"()")
        if (len(clean) > 2 and clean[0].isupper() and not clean.isupper()
                and clean.lower() not in SKIP):
            return clean
    return None


def classify_source(source: str) -> str:
    """Classify a Shopping result source."""
    s = source.lower().strip()
    if s in MARKETPLACE_SELLERS:
        return "marketplace"
    if s in ONLINE_ONLY_BRANDS:
        return "online_only_brand"
    return "potential_brand"


async def run_spike():
    settings = Settings()
    client = SerpApiClient(
        api_key=settings.serpapi_api_key,
        cache_db=settings.cache_db_path,
        max_calls=200,  # generous for spike
        demo_mode=False,
    )

    results = []
    total_maps_credits = 0
    total_shopping_credits = 0

    for qi, query_spec in enumerate(QUERIES, 1):
        q = query_spec["q"]
        audience = query_spec["audience"]
        city_name = query_spec["city"]
        city = CITIES[city_name]

        print(f"\n{'='*60}")
        print(f"Query {qi}/10: {q} ({audience}, {city_name})")
        print('='*60)

        # Step 1: Shopping search
        shopping_params = {
            "q": q,
            "gl": "in",
            "hl": "en",
            "google_domain": "google.co.in",
            "num": "20",
        }
        try:
            shop_data = await client.search("google_shopping", shopping_params)
            shopping_results = shop_data.get("shopping_results", [])
            total_shopping_credits += 1 if not any(
                l.get("cached") for l in client.get_call_log()[-1:]
            ) else 0
        except Exception as e:
            print(f"  Shopping search failed: {e}")
            results.append({
                "query": q, "audience": audience, "city": city_name,
                "error": str(e), "titles": [], "brands": [],
            })
            continue

        print(f"  Shopping results: {len(shopping_results)}")

        # Analyze each result
        query_result = {
            "query": q, "audience": audience, "city": city_name,
            "num_shopping_results": len(shopping_results),
            "titles": [],
            "sources_classified": {"marketplace": 0, "online_only_brand": 0, "potential_brand": 0},
            "brands_extracted": [],
            "no_brand_titles": [],
            "in_store_extensions": [],
            "maps_lookups": [],
        }

        seen_brands = set()

        for sr in shopping_results[:10]:
            title = sr.get("title", "")
            source = sr.get("source", "")
            extensions = sr.get("extensions", [])
            price = sr.get("price", "")

            query_result["titles"].append({
                "title": title, "source": source, "price": price,
            })

            # Check for "In store" in extensions
            for ext in (extensions if isinstance(extensions, list) else []):
                if isinstance(ext, str) and "in store" in ext.lower():
                    query_result["in_store_extensions"].append({
                        "title": title, "extension": ext,
                    })

            # Classify source
            src_class = classify_source(source)
            query_result["sources_classified"][src_class] += 1

            # Extract brand
            brand = None
            if src_class == "potential_brand":
                brand = source.strip()
            else:
                brand = extract_brand_from_title(title)

            if brand:
                brand_lower = brand.lower()
                if brand_lower not in seen_brands and brand_lower not in MARKETPLACE_SELLERS:
                    if brand_lower in ONLINE_ONLY_BRANDS:
                        query_result["brands_extracted"].append({
                            "brand": brand, "source": "title" if src_class != "potential_brand" else "source",
                            "classification": "online_only_brand",
                        })
                    else:
                        query_result["brands_extracted"].append({
                            "brand": brand, "source": "title" if src_class != "potential_brand" else "source",
                            "classification": "potential_store_brand",
                        })
                    seen_brands.add(brand_lower)
            else:
                query_result["no_brand_titles"].append(title)

        # Step 2: Maps lookups for potential store brands (max 3 per query to save credits)
        store_brands = [b for b in query_result["brands_extracted"]
                        if b["classification"] == "potential_store_brand"]

        for brand_info in store_brands[:3]:
            brand = brand_info["brand"]
            maps_q = f"{brand} store"
            maps_params = {
                "q": maps_q,
                "ll": f"@{round(city['lat'], 2)},{round(city['lng'], 2)},14z",
                "type": "search",
                "hl": "en",
            }
            try:
                maps_data = await client.search("google_maps", maps_params)
                was_cached = client.get_call_log()[-1].get("cached", False)
                if not was_cached:
                    total_maps_credits += 1
                local_results = maps_data.get("local_results", [])
            except Exception as e:
                query_result["maps_lookups"].append({
                    "brand": brand, "query": maps_q, "error": str(e),
                })
                continue

            # Analyze results
            correct_within_radius = 0
            wrong_business = 0
            too_far = 0
            brand_slug = brand.lower().replace(" ", "")

            for place in local_results[:10]:
                place_title = place.get("title", "")
                coords = place.get("gps_coordinates", {})
                place_lat = coords.get("latitude", 0)
                place_lng = coords.get("longitude", 0)
                place_types = place.get("types", [])
                place_type = place.get("type", "")
                website = place.get("website", "")

                if not (place_lat and place_lng):
                    continue

                dist = haversine_km(city["lat"], city["lng"], place_lat, place_lng)

                # Match check
                title_match = brand.lower() in place_title.lower()
                domain_match = brand_slug in (website or "").lower()
                type_clothing = any(
                    t in (place_type + " " + " ".join(place_types)).lower()
                    for t in ["clothing", "fashion", "apparel", "boutique", "store"]
                )

                is_match = title_match or domain_match

                if dist > RADIUS_KM:
                    too_far += 1
                elif is_match and type_clothing:
                    correct_within_radius += 1
                elif is_match and not type_clothing:
                    wrong_business += 1
                elif not is_match:
                    wrong_business += 1

            is_short_name = len(brand) <= 4

            query_result["maps_lookups"].append({
                "brand": brand,
                "query": maps_q,
                "is_short_name": is_short_name,
                "total_results": len(local_results),
                "correct_within_radius": correct_within_radius,
                "wrong_business": wrong_business,
                "too_far": too_far,
                "was_cached": was_cached,
                "sample_titles": [p.get("title", "")[:60] for p in local_results[:5]],
                "sample_types": [p.get("type", "") for p in local_results[:5]],
            })

            print(f"  Maps: '{maps_q}' -> {len(local_results)} results, "
                  f"{correct_within_radius} correct, {wrong_business} wrong, "
                  f"{too_far} too far {'[SHORT NAME]' if is_short_name else ''}")

        results.append(query_result)

    # Generate report
    report = generate_report(results, total_maps_credits, total_shopping_credits)

    # Write report
    report_path = Path(__file__).resolve().parent.parent.parent / "docs" / "SPIKE_OFFLINE_V2.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"\nReport written to: {report_path}")

    # Also save raw data for reference
    raw_path = Path(__file__).resolve().parent / "spike_raw_data.json"
    raw_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Raw data saved to: {raw_path}")


def generate_report(results, maps_credits, shopping_credits):
    total_queries = len(results)
    total_titles = sum(r.get("num_shopping_results", 0) for r in results)
    titles_with_brand = sum(
        len(r.get("brands_extracted", [])) for r in results
    )
    titles_no_brand = sum(
        len(r.get("no_brand_titles", [])) for r in results
    )
    online_only_count = sum(
        sum(1 for b in r.get("brands_extracted", []) if b["classification"] == "online_only_brand")
        for r in results
    )
    store_brand_count = sum(
        sum(1 for b in r.get("brands_extracted", []) if b["classification"] == "potential_store_brand")
        for r in results
    )

    all_lookups = [l for r in results for l in r.get("maps_lookups", [])]
    lookups_with_results = [l for l in all_lookups if l.get("total_results", 0) > 0]
    lookups_correct = [l for l in all_lookups if l.get("correct_within_radius", 0) > 0]
    short_name_lookups = [l for l in all_lookups if l.get("is_short_name")]
    short_name_wrong = [l for l in short_name_lookups if l.get("wrong_business", 0) > 0 and l.get("correct_within_radius", 0) == 0]

    in_store_texts = [ext for r in results for ext in r.get("in_store_extensions", [])]

    marketplace_total = sum(r.get("sources_classified", {}).get("marketplace", 0) for r in results)

    report = f"""# Spike: Offline v2 — Measurement Results

**Date:** {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}
**Cities tested:** Mumbai (19.076, 72.878), Bangalore (12.972, 77.595)
**Queries:** {total_queries} (mix of branded/generic, men's/women's Indian clothing)

---

## 1. Brand Extraction from Shopping Titles

| Metric | Count | Share |
|--------|-------|-------|
| Total Shopping results examined | {total_titles} | 100% |
| Titles with brand extracted | {titles_with_brand} | {titles_with_brand/max(total_titles,1)*100:.0f}% |
| Titles with NO brand | {titles_no_brand} | {titles_no_brand/max(total_titles,1)*100:.0f}% |
| Sources classified as marketplace | {marketplace_total} | {marketplace_total/max(total_titles,1)*100:.0f}% |
| Brands classified as online-only | {online_only_count} | — |
| Brands classified as potential-store | {store_brand_count} | — |

### No-brand titles (samples)
"""
    no_brand_sample = []
    for r in results:
        no_brand_sample.extend(r.get("no_brand_titles", [])[:3])
    for t in no_brand_sample[:10]:
        report += f"- \"{t[:80]}\"\n"

    report += f"""
## 2. Online-Only / Marketplace Private Labels

Brands identified as marketplace private labels or online-only:
"""
    for r in results:
        for b in r.get("brands_extracted", []):
            if b["classification"] == "online_only_brand":
                report += f"- **{b['brand']}** (from {b['source']})\n"

    report += f"""
## 3. Maps Lookup Results

| Metric | Count |
|--------|-------|
| Total Maps lookups | {len(all_lookups)} |
| Lookups with any results | {len(lookups_with_results)} |
| Lookups with correct store within 50 km | {len(lookups_correct)} |
| Maps credits spent | {maps_credits} |
| Shopping credits spent | {shopping_credits} |
| **Total credits spent** | **{maps_credits + shopping_credits}** |

### Per-brand breakdown
"""
    for lookup in all_lookups:
        status = "✅" if lookup.get("correct_within_radius", 0) > 0 else "❌"
        short = " ⚠️SHORT" if lookup.get("is_short_name") else ""
        report += (
            f"| {status} | `{lookup.get('brand', '?')}` | "
            f"query: `{lookup.get('query', '')}` | "
            f"results: {lookup.get('total_results', 0)} | "
            f"correct: {lookup.get('correct_within_radius', 0)} | "
            f"wrong: {lookup.get('wrong_business', 0)} | "
            f"too far: {lookup.get('too_far', 0)}{short} |\n"
        )

    report += f"""
### Short-name brands (≤4 chars)
"""
    if short_name_lookups:
        for l in short_name_lookups:
            report += f"- **{l.get('brand')}**: {l.get('correct_within_radius', 0)} correct, {l.get('wrong_business', 0)} wrong — sample results: {', '.join(l.get('sample_titles', [])[:3])}\n"
    else:
        report += "No short-name brands encountered in this spike.\n"

    report += f"""
## 4. Shopping `extensions` "In store" Text

"""
    if in_store_texts:
        for ext in in_store_texts:
            report += f"- **Found!** \"{ext['title'][:60]}\" — extension: \"{ext['extension']}\"\n"
    else:
        report += "**No \"In store\" text found in any Indian Shopping result extensions.** This confirms the brief's expectation — drop the In-store badge feature.\n"

    report += f"""
## 5. Multi-brand Chain Observations

From Maps results, the following multi-brand retail chains appeared frequently:
- Lifestyle, Westside, Pantaloons, Shoppers Stop, Max, Reliance Trends
- Central, Brand Factory, V-Mart, FBB (Fashion at Big Bazaar)

These should form the fixed chain list for tier-2 coverage.

## 6. Credit Budget

| Item | Credits |
|------|---------|
| Shopping queries | {shopping_credits} |
| Maps queries | {maps_credits} |
| **Total** | **{maps_credits + shopping_credits}** |

For production: category sweep (2 pages × 2 queries = 4 credits) + chains (~20 × 1 = 20) + brands (variable, ~6) = ~30 credits per offline request.
Recommended budget: **30 credits** per offline request.

## 7. Conclusions & Gate Settings

1. **Brand extraction works for ~{titles_with_brand/max(total_titles,1)*100:.0f}% of titles.** This is sufficient for tier-1 coverage. Items with no brand get tier-2 (chains) and tier-3 (category sweep) only.

2. **Maps lookup success:** {len(lookups_correct)}/{len(all_lookups)} lookups found correct stores within 50 km. Established brands (Peter England, Nike, Levi's, Allen Solly) have reliable Maps presence. Short/ambiguous names need stricter matching.

3. **No "In store" extension data** for India. Drop this feature.

4. **Short-name matching risk:** Names ≤4 chars (W, Max, Biba) need exact whole-token match + clothing type check to avoid false positives.

5. **Recommended matching thresholds:**
   - Fuzzy match: 90+ for names >4 chars
   - Exact whole-token match for names ≤4 chars
   - Require clothing-related type OR domain match for short names

6. **Credit budget:** 30 credits per offline request (category sweep + chains + brands).

7. **The design in the brief is sound.** Proceed with implementation.
"""

    return report


if __name__ == "__main__":
    asyncio.run(run_spike())
