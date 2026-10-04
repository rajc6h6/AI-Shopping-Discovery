"""Compare-prices subagent: searches multiple platforms for the same product."""

from app.models import (
    CompareOffer, CompareResult, ParsedItem, ProductCandidate, VerificationResult,
)
from app.serpapi_client import SerpApiClient
from app.verifier import verify_match


def _build_compare_queries(title: str, attributes: dict, market: str) -> list[dict]:
    """Build search queries for different platforms."""
    search_term = title[:80]  # Truncate for search
    queries = []

    # Google Shopping (broader query for price comparison)
    gs_params = {"q": search_term, "gl": market, "hl": "en", "num": 5}
    if market == "in":
        gs_params["google_domain"] = "google.co.in"
    queries.append({"engine": "google_shopping", "params": gs_params})

    # Amazon
    amazon_domain = "amazon.in" if market == "in" else "amazon.com"
    queries.append({
        "engine": "amazon",
        "params": {"search_term": search_term, "amazon_domain": amazon_domain},
    })

    # eBay (global)
    queries.append({
        "engine": "ebay",
        "params": {"_nkw": search_term, "ebay_domain": "ebay.com"},
    })

    # Walmart (US only — not available in India)
    if market == "us":
        queries.append({
            "engine": "walmart",
            "params": {"query": search_term},
        })

    return queries


def _extract_results(engine: str, data: dict) -> list[dict]:
    """Extract product results from different engine response formats."""
    if engine == "google_shopping":
        return data.get("shopping_results", [])
    elif engine == "amazon":
        return data.get("organic_results", [])
    elif engine == "ebay":
        return data.get("organic_results", [])
    elif engine == "walmart":
        return data.get("organic_results", [])
    return []


async def compare_prices(
    product_title: str,
    product_attributes: dict,
    client: SerpApiClient,
    market: str = "in",
    audience: str = "",
) -> CompareResult:
    """
    Search multiple platforms for the same product and return
    verified, price-sorted offers.
    """
    queries = _build_compare_queries(product_title, product_attributes, market)
    offers: list[CompareOffer] = []
    engines_used: list[str] = []

    # Build a reference ParsedItem for verification
    ref_item = ParsedItem(
        category=product_attributes.get("category", "product"),
        brand=product_attributes.get("brand"),
        model_name=product_attributes.get("model_name"),
        colour=product_attributes.get("colour"),
        material=product_attributes.get("material"),
        gender=audience if audience else product_attributes.get("gender"),
        is_specific=bool(product_attributes.get("brand") and product_attributes.get("model_name")),
        source_text=product_title,
        search_query=product_title,
    )

    for query in queries:
        engine = query["engine"]
        engines_used.append(engine)

        try:
            data = await client.search(engine, query["params"])
        except Exception:
            continue  # Skip failed engines, partial results > no results

        results = _extract_results(engine, data)
        currency = "INR" if market == "in" else "USD"

        for r in results[:3]:  # Top 3 per platform to bound cost
            candidate = ProductCandidate(
                title=r.get("title", ""),
                price=r.get("price"),
                extracted_price=r.get("extracted_price"),
                currency=currency,
                source=r.get("source", r.get("seller", engine)),
                link=r.get("link", ""),
                thumbnail=r.get("thumbnail"),
                engine_used=engine,
                position=r.get("position", 0),
            )

            verification = verify_match(ref_item, candidate, audience)

            # Only include if confidence is reasonable (>0.4)
            if verification.overall_confidence >= 0.4:
                platform_display = {
                    "google_shopping": "Google Shopping",
                    "amazon": f"Amazon {'India' if market == 'in' else 'US'}",
                    "ebay": "eBay",
                    "walmart": "Walmart",
                }.get(engine, engine)

                offers.append(CompareOffer(
                    platform=platform_display,
                    seller=candidate.source,
                    price=candidate.price,
                    extracted_price=candidate.extracted_price,
                    currency=currency,
                    link=candidate.link,
                    verified=verification.overall_confidence >= 0.6,
                    verification=verification,
                ))

    # Sort by price (cheapest first), None prices at end
    offers_priced = sorted(
        [o for o in offers if o.extracted_price is not None],
        key=lambda o: o.extracted_price,
    )
    offers_unpriced = [o for o in offers if o.extracted_price is None]
    sorted_offers = offers_priced + offers_unpriced

    cheapest_idx = 0 if offers_priced else None

    return CompareResult(
        offers=sorted_offers,
        cheapest_index=cheapest_idx,
        search_engines_used=engines_used,
    )
