"""Product discovery via SerpApi Google Shopping."""

from app.models import ParsedItem, ProductCandidate
from app.serpapi_client import SerpApiClient

# Gender word to inject into queries for non-neutral categories
AUDIENCE_WORDS: dict[str, str] = {"male": "men", "female": "women"}

# Categories where injecting a gender word into the query hurts results
GENDER_NEUTRAL_FINDER = {
    'phone', 'smartphone', 'laptop', 'tablet', 'watch', 'bag', 'backpack',
    'wallet', 'sunglasses', 'belt', 'hat', 'cap', 'earphones', 'headphones',
    'earbuds', 'perfume', 'fragrance', 'keyboard', 'mouse', 'monitor',
}


def _build_shopping_params(
    item: ParsedItem,
    market: str = "in",
    audience: str = "",
) -> dict:
    """Build Google Shopping API parameters for a parsed item.

    When audience is provided and the category is not gender-neutral,
    the audience word ("men"/"women") is prepended to the query if not already present.
    """
    query = item.search_query

    if audience:
        word = AUDIENCE_WORDS.get(audience, "")
        category_norm = item.category.lower()
        is_neutral = any(neutral in category_norm for neutral in GENDER_NEUTRAL_FINDER)
        if not is_neutral and word and word not in query.lower():
            query = f"{word} {query}"

    params = {
        "q": query,
        "gl": market,
        "hl": "en",
        "num": 10,
    }
    if market == "in":
        params["google_domain"] = "google.co.in"
    return params


async def find_products(
    item: ParsedItem,
    client: SerpApiClient,
    market: str = "in",
    audience: str = "",
) -> list[ProductCandidate]:
    """
    Search Google Shopping for products matching a parsed item.
    Returns ranked ProductCandidate list.
    """
    params = _build_shopping_params(item, market, audience)
    data = await client.search("google_shopping", params)

    candidates = []
    currency = "INR" if market == "in" else "USD"

    for result in data.get("shopping_results", [])[:10]:
        candidates.append(
            ProductCandidate(
                title=result.get("title", "Unknown Product"),
                price=result.get("price"),
                extracted_price=result.get("extracted_price"),
                currency=currency,
                source=result.get("source", "Unknown Seller"),
                # product_link is the real URL; link is often empty for shopping results
                link=result.get("product_link") or result.get("link", ""),
                thumbnail=result.get("thumbnail"),
                rating=result.get("rating"),
                reviews=result.get("reviews"),
                product_id=result.get("product_id"),
                immersive_product_page_token=result.get("immersive_product_page_token"),
                engine_used="google_shopping",
                position=result.get("position", 0),
            )
        )

    return candidates
