"""Compare-prices subagent: searches multiple platforms for the same product."""

from typing import Optional
from app.models import (
    CompareOffer, CompareResult, ParsedItem, ProductCandidate, VerificationResult,
)
from app.serpapi_client import SerpApiClient

async def compare_prices(
    product_title: str,
    product_attributes: dict,
    client: SerpApiClient,
    market: str = "in",
    audience: str = "",
    product_id: Optional[str] = None,
    immersive_product_page_token: Optional[str] = None,
    trace_callback=None,
) -> CompareResult:
    """
    Search multiple platforms for the same product and return
    verified, price-sorted offers.
    """
    offers: list[CompareOffer] = []
    engines_used: list[str] = []
    
    currency = "INR" if market == "in" else "USD"

    # Primary: google_immersive_product
    if immersive_product_page_token:
        engines_used.append("google_immersive_product")
        if trace_callback:
            await trace_callback("fetching sellers", "Google Immersive Product")
        try:
            data = await client.search("google_immersive_product", {
                "immersive_product_page_token": immersive_product_page_token,
                "gl": market,
                "hl": "en",
            })
            sellers = data.get("sellers", [])
            for seller in sellers:
                extracted_price = seller.get("extracted_price")
                if extracted_price is None and seller.get("extracted_base_price"):
                    extracted_price = seller.get("extracted_base_price")
                
                offers.append(CompareOffer(
                    platform="Google Immersive Product",
                    seller=seller.get("name", seller.get("seller", "Unknown")),
                    price=seller.get("price"),
                    extracted_price=extracted_price,
                    currency=currency,
                    link=seller.get("link", ""),
                    verified=True,  # Same product page, so verified
                    verification=None,
                    shipping_info=seller.get("shipping", ""),
                ))
            if trace_callback:
                await trace_callback(f"found {len(offers)} sellers", "Google Immersive Product")
        except Exception:
            pass

    # Fallback 1: google_product
    if not offers and product_id:
        engines_used.append("google_product")
        if trace_callback:
            await trace_callback("falling back to Google Product", "Google Product")
        try:
            data = await client.search("google_product", {
                "product_id": product_id,
                "gl": market,
                "hl": "en",
            })
            sellers = data.get("sellers_results", {}).get("online_sellers", [])
            for seller in sellers:
                extracted_price = seller.get("extracted_total_price")
                if extracted_price is None:
                    extracted_price = seller.get("extracted_base_price")
                    
                offers.append(CompareOffer(
                    platform="Google Product",
                    seller=seller.get("name", "Unknown"),
                    price=seller.get("total_price") or seller.get("price"),
                    extracted_price=extracted_price,
                    currency=currency,
                    link=seller.get("link", ""),
                    verified=True,  # Same product ID, so verified
                    verification=None,
                ))
            if trace_callback:
                await trace_callback(f"found {len(offers)} sellers", "Google Product")
        except Exception:
            pass

    # Fallback 2: google_shopping (Similar listings)
    if not offers:
        engines_used.append("google_shopping")
        if trace_callback:
            await trace_callback("falling back to Google Shopping", "Google Shopping")
        try:
            search_term = product_title[:80]
            gs_params = {"q": search_term, "gl": market, "hl": "en", "num": 10}
            if market == "in":
                gs_params["google_domain"] = "google.co.in"

            data = await client.search("google_shopping", gs_params)
            results = data.get("shopping_results", [])
            
            for r in results:
                seller = r.get("source", "Unknown Seller")
                offers.append(CompareOffer(
                    platform="Google Shopping (Similar listings)",
                    seller=seller,
                    price=r.get("price"),
                    extracted_price=r.get("extracted_price"),
                    currency=currency,
                    link=r.get("product_link") or r.get("link", ""),
                    verified=False,  # Needs verification
                    verification=None,
                ))
            if trace_callback:
                await trace_callback(f"found {len(offers)} sellers", "Google Shopping")
        except Exception:
            pass

    # Drop duplicate sellers (keep lowest price), drop entries with no link
    filtered_offers = []
    seen_sellers = set()
    
    # Sort ascending by extracted_price to keep the lowest priced one when dropping duplicates
    priced_offers = sorted(
        [o for o in offers if o.extracted_price is not None and o.link],
        key=lambda o: o.extracted_price
    )
    unpriced_offers = [o for o in offers if o.extracted_price is None and o.link]
    
    for offer in priced_offers + unpriced_offers:
        if offer.seller not in seen_sellers:
            seen_sellers.add(offer.seller)
            filtered_offers.append(offer)

    cheapest_idx = 0 if len(priced_offers) > 0 and filtered_offers and filtered_offers[0].extracted_price is not None else None

    return CompareResult(
        offers=filtered_offers,
        cheapest_index=cheapest_idx,
        search_engines_used=engines_used,
    )
