# Offline Brand Logic Plan

## Summary (required first report)

When a Offline item is **generic** (no named brand), we extract brands from its verified online candidates and use those to search Maps.

**Brand-selection algorithm:**

1. **Source of brands**: For each `ProductCandidate` in the verified results for this item:
   - Use `candidate.source` field as a brand candidate
   - Also regex-extract the first capitalised word(s) from `candidate.title` that precede a common product noun (e.g. "Nike Air Force 1 Sneakers" → "Nike")
2. **Brand vs. seller filter**: Remove sources/titles that match the `MARKETPLACE_SELLERS` set (Amazon, Flipkart, Myntra, Meesho, Snapdeal, eBay, Nykaa, AJIO, Shein, Temu, etc.). What remains is a brand candidate.
3. **Quality filter**: Only candidates with `verification.overall_confidence >= 0.5` contribute brand candidates.
4. **Deduplication & ranking**: Group by normalised brand name (case-insensitive). Score = `sum(confidence)` across contributing candidates. Discard brands that appear only once with max confidence < 0.6.
5. **Cap**: Take the top 3 brands by score. Deterministic: ties broken alphabetically.
6. **Fallback**: If 0 brands pass the filter, the offline search is skipped and the UI shows: *"No brand could be identified from the online results — try searching for a specific brand."*

**Budget impact**: Generic-item offline uses 3 Maps calls (1 per brand), down from 5 (1 per seller). Stays inside `max_calls_per_offline = 5`.

---

## Detailed Design

### Inputs
- `item: ParsedItem` — the item being searched offline (is_specific=False, brand=None)
- `verified_results: list[dict]` — the online results for this item, format:
  ```
  {"candidate": ProductCandidate.model_dump(), "verification": VerificationResult.model_dump()}
  ```

### The `MARKETPLACE_SELLERS` constant
```python
MARKETPLACE_SELLERS = {
    'amazon', 'amazon india', 'amazon.in', 'amazon.com',
    'flipkart', 'myntra', 'ajio', 'nykaa', 'nykaa fashion',
    'meesho', 'snapdeal', 'shopclues', 'shein', 'temu',
    'alibaba', 'aliexpress', 'wish', 'ebay', 'etsy',
    'google shopping', 'google', 'walmart', 'target',
    'paytm mall', 'tata cliq', 'reliance digital',
}
```

### Brand extraction from title (regex fallback)
```python
import re
PRODUCT_NOUNS = {'sneakers','shoes','boots','shirt','tshirt','jacket',
                 'blazer','chinos','jeans','pants','kurta','dress',
                 'bag','watch','belt','sunglasses'}

def extract_brand_from_title(title: str) -> str | None:
    """Extract leading brand-like token(s) before a product noun."""
    words = title.split()
    for i, word in enumerate(words):
        if word.lower() in PRODUCT_NOUNS and i > 0:
            # Take up to 2 preceding words as brand
            return ' '.join(words[max(0, i-2):i])
    # Fallback: first capitalised word (not ALL CAPS)
    for word in words:
        if word[0].isupper() and not word.isupper() and len(word) > 2:
            return word
    return None
```

### `extract_brands_from_results(verified_results, min_confidence=0.5)` function signature
```python
def extract_brands_from_results(
    verified_results: list[dict],
    min_confidence: float = 0.5,
    min_single_confidence: float = 0.6,
    max_brands: int = 3,
) -> list[str]:
    """
    Returns a ranked list of brand names (max `max_brands`) from verified online results.
    Returns [] if no usable brands found.
    """
```

### Maps query for brand mode
```python
# Specific item: existing seller path unchanged
# Generic item:
q = f"{brand} store {audience_word}"  # e.g. "Nike store men"
```

### UI brand-source note
In the Offline mode panel, when generic brands are used:
> *"Brands taken from your online matches: Nike, Adidas, Puma"*

### Evidence text for brand-mode store cards
```python
f"{brand} store. {brand} appears in your online matches at {price}."
```
If no price available: `f"{brand} store. {brand} appears in your online matches."`

### No-brand fallback UI
```
⚠ No brand could be identified from the online results.
  Try searching for a specific brand name.
```

---

## Decisions

| # | Decision | Choice | Reason |
|---|----------|--------|--------|
| D27 | Brand extraction primary source | `candidate.source` field | SerpApi returns seller/brand here; most reliable |
| D28 | Title regex fallback | First capitalised tokens before product noun | Handles cases where source is a marketplace |
| D29 | Marketplace filter | Fixed set `MARKETPLACE_SELLERS` | Deterministic, no LLM cost, covers known cases |
| D30 | Confidence threshold | 0.5 for contributing, 0.6 for single-occurrence | Prevents weak matches polluting brand list |
| D31 | Brand cap | 3 | Budget: 3 Maps calls vs. 5 for seller path; both within 5-call cap |
| D32 | Ranking score | `sum(confidence)` across candidates | Simple, deterministic, rewards brands with multiple strong matches |
| D33 | Store type labelling | `store_type` from Maps `types[]` field used to label "Brand store" vs "Retailer" | Maps often returns this; label honestly, don't invent |
| D34 | No-coordinates stores | Excluded (same as radius rule) | Cannot verify within 50 km |
| D35 | No-brand fallback | Static message, no search | Do not search on description — Maps returns noise |
