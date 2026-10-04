"""
Brand extractor for generic offline items.

Extracts and ranks brands from verified online candidates.
Never invents brands — only uses data already present in candidates.
"""

MARKETPLACE_SELLERS = {
    'amazon', 'amazon india', 'amazon.in', 'amazon.com',
    'flipkart', 'myntra', 'ajio', 'nykaa', 'nykaa fashion',
    'meesho', 'snapdeal', 'shopclues', 'shein', 'temu',
    'alibaba', 'aliexpress', 'wish', 'ebay', 'etsy',
    'google shopping', 'google', 'walmart', 'target',
    'paytm mall', 'tata cliq', 'reliance digital', 'croma', 'vijay sales',
}

PRODUCT_NOUNS = {
    'sneakers', 'shoes', 'boots', 'loafers', 'sandals', 'heels', 'flats',
    'shirt', 'tshirt', 't-shirt', 'jacket', 'blazer', 'chinos', 'jeans',
    'pants', 'trousers', 'kurta', 'dress', 'top', 'hoodie', 'sweater',
    'bag', 'watch', 'belt', 'sunglasses', 'cap', 'hat', 'shorts', 'skirt',
    'leggings', 'saree', 'kurti', 'kurti',
}

_SKIP_WORDS = {'men', "men's", 'women', "women's", 'unisex', 'new',
               'black', 'white', 'blue', 'red', 'navy', 'grey', 'gray',
               'beige', 'pink', 'green', 'casual', 'formal', 'classic'}

_COMMON_WORDS = {'the', 'for', 'and', 'with', 'a', 'an', 'in', 'of', 'to', 'best', 'buy'}


def _is_marketplace(name: str) -> bool:
    return name.lower().strip() in MARKETPLACE_SELLERS


def _extract_brand_from_title(title: str) -> str | None:
    """Extract a leading brand-like token from a product title."""
    words = title.split()
    for i, word in enumerate(words):
        if word.lower().rstrip('s') in PRODUCT_NOUNS and i > 0:
            candidates = [w for w in words[max(0, i - 2):i]
                          if w.lower() not in _SKIP_WORDS and len(w) > 1]
            if candidates:
                return ' '.join(candidates)
    # Fallback: first capitalised word that is not a generic term
    for word in words:
        if (word[0].isupper() and not word.isupper() and len(word) > 2
                and word.lower() not in _COMMON_WORDS | _SKIP_WORDS):
            return word
    return None


def extract_brands_from_results(
    verified_results: list[dict],
    audience: str,
    min_confidence: float = 0.5,
    min_single_confidence: float = 0.6,
    max_brands: int = 3,
) -> list[str]:
    """
    Extract and rank brands from verified online candidates for a generic item.

    Args:
        verified_results: list of {candidate: dict, verification: dict}
        audience: "male" or "female" (for future query construction, not filtering here)
        min_confidence: minimum overall_confidence for a candidate to contribute
        min_single_confidence: minimum confidence when a brand appears only once
        max_brands: maximum number of brands to return

    Returns:
        Ranked list of brand names (highest confidence-sum first), len <= max_brands.
        Returns [] if no usable brands found.
    """
    # brand_lower -> list of confidence scores
    brand_scores: dict[str, list[float]] = {}
    # brand_lower -> original casing from first occurrence
    brand_originals: dict[str, str] = {}

    for result in verified_results:
        conf = result.get("verification", {}).get("overall_confidence", 0.0)
        if conf < min_confidence:
            continue

        candidate = result.get("candidate", {})
        source = candidate.get("source", "")
        title = candidate.get("title", "")

        brand_name: str | None = None

        # Prefer source field — most reliable
        if source and not _is_marketplace(source):
            brand_name = source.strip()
        elif title:
            extracted = _extract_brand_from_title(title)
            if extracted and not _is_marketplace(extracted):
                brand_name = extracted

        if brand_name:
            key = brand_name.lower()
            if key not in brand_scores:
                brand_scores[key] = []
                brand_originals[key] = brand_name  # first-seen casing wins
            brand_scores[key].append(conf)

    # Apply single-occurrence minimum confidence filter and compute rank score
    ranked: list[tuple[str, float]] = []
    for key, confs in brand_scores.items():
        if len(confs) == 1 and confs[0] < min_single_confidence:
            continue
        ranked.append((key, sum(confs)))

    # Sort: highest score first; alphabetical to break ties (deterministic)
    ranked.sort(key=lambda x: (-x[1], x[0]))

    return [brand_originals[k] for k, _ in ranked[:max_brands]]
