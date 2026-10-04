"""
Per-attribute confidence scorer and match verifier.

Scores each product candidate against the parsed item's attributes.
Uses rule-based matching (deterministic, fast, calibratable).
"""

import re
from app.models import ParsedItem, ProductCandidate, AttributeScore, VerificationResult


# Categories where audience gender check is skipped — gender words in titles
# for these categories usually refer to sizing or colour, not the product's gender.
GENDER_NEUTRAL_CATEGORIES = {
    'phone', 'smartphone', 'laptop', 'tablet', 'watch', 'bag', 'backpack',
    'wallet', 'sunglasses', 'belt', 'hat', 'cap', 'water bottle', 'earphones',
    'headphones', 'earbuds', 'perfume', 'fragrance', 'jewellery', 'jewelry',
    'earrings', 'necklace', 'bracelet', 'keyboard', 'mouse', 'monitor',
}

MALE_WORDS = {'men', "men's", 'male', "man's", 'gents', 'boys', 'boy'}
FEMALE_WORDS = {'women', "women's", 'female', "woman's", 'ladies', 'girls', 'girl'}


# Synonym groups for fuzzy matching
SYNONYMS = {
    # Colours
    "navy": ["dark blue", "navy blue", "midnight blue"],
    "white": ["ivory", "off-white", "cream", "off white"],
    "black": ["onyx", "jet black", "charcoal"],
    "beige": ["tan", "khaki", "sand", "camel"],
    "brown": ["chocolate", "coffee", "chestnut", "cognac"],
    "grey": ["gray", "charcoal", "slate", "heather"],
    "red": ["crimson", "burgundy", "maroon", "wine"],
    "blue": ["cobalt", "royal blue", "sky blue", "teal"],
    "green": ["olive", "forest", "sage", "emerald", "moss"],
    "pink": ["blush", "rose", "coral", "salmon"],
    # Categories
    "sneakers": ["shoes", "trainers", "kicks", "athletic shoes", "running shoes"],
    "chinos": ["pants", "trousers", "khakis"],
    "overshirt": ["shirt jacket", "shacket", "over shirt", "over-shirt"],
    "t-shirt": ["tee", "t shirt", "tshirt"],
    "jeans": ["denim", "denim pants"],
    "blazer": ["sport coat", "suit jacket"],
    "jacket": ["coat", "outerwear"],
    "watch": ["timepiece", "wristwatch"],
    "sunglasses": ["shades", "sunnies"],
    "belt": ["leather belt", "waist belt"],
    "boots": ["ankle boots", "chelsea boots"],
    # Fit/style
    "slim": ["skinny", "tapered", "fitted", "slim fit", "slim-fit"],
    "oversized": ["loose", "relaxed", "baggy", "loose fit"],
    "minimalist": ["minimal", "clean", "simple"],
    # Materials
    "leather": ["faux leather", "pu leather", "genuine leather", "full grain leather"],
    "linen": ["flax"],
    "cotton": ["organic cotton"],
    "denim": ["raw denim", "selvedge"],
    "suede": ["nubuck"],
}


def _normalise(text: str) -> str:
    """Lowercase and strip extra whitespace."""
    return " ".join(text.lower().split())


def _check_attribute(name: str, expected: str | None, title: str) -> AttributeScore:
    """Check if an expected attribute appears in the product title."""
    if expected is None:
        return AttributeScore(
            attribute=name,
            match=True,
            confidence=1.0,
            evidence="Not specified in request — any value acceptable",
        )

    title_norm = _normalise(title)
    expected_norm = _normalise(expected)

    # Direct substring match
    if expected_norm in title_norm:
        return AttributeScore(
            attribute=name,
            match=True,
            confidence=0.95,
            evidence=f"'{expected}' found in product title",
        )

    # Synonym matching
    for synonym in SYNONYMS.get(expected_norm, []):
        if synonym in title_norm:
            return AttributeScore(
                attribute=name,
                match=True,
                confidence=0.80,
                evidence=f"Synonym '{synonym}' found in title (matches '{expected}')",
            )

    # Check if expected is a synonym of something else
    for canonical, syns in SYNONYMS.items():
        if expected_norm in syns and canonical in title_norm:
            return AttributeScore(
                attribute=name,
                match=True,
                confidence=0.80,
                evidence=f"Canonical form '{canonical}' found (synonym of '{expected}')",
            )

    # Word-level partial match (any word from expected appears in title)
    expected_words = set(expected_norm.split())
    title_words = set(title_norm.split())
    overlap = expected_words & title_words
    if overlap and len(overlap) / len(expected_words) >= 0.5:
        return AttributeScore(
            attribute=name,
            match=True,
            confidence=0.60,
            evidence=f"Partial word match: {overlap} found in title",
        )

    return AttributeScore(
        attribute=name,
        match=False,
        confidence=0.10,
        evidence=f"'{expected}' not found in product title",
    )


def _check_price_band(budget_hint: str, price: float) -> AttributeScore:
    """Check if price falls within the budget hint."""
    numbers = re.findall(r"[\d,]+\.?\d*", budget_hint.replace(",", ""))
    if not numbers:
        return AttributeScore(
            attribute="price_band",
            match=True,
            confidence=0.50,
            evidence="Could not parse budget hint",
        )

    nums = [float(n) for n in numbers]

    if len(nums) == 1:
        target = nums[0]
        if target == 0:
            return AttributeScore(
                attribute="price_band", match=True, confidence=0.50,
                evidence="Budget target is zero — skipping",
            )
        ratio = min(price, target) / max(price, target)
        match = ratio > 0.5
        return AttributeScore(
            attribute="price_band",
            match=match,
            confidence=round(ratio, 2),
            evidence=f"Price {price} vs budget ~{target} (ratio {ratio:.0%})",
        )
    else:
        low, high = min(nums), max(nums)
        match = low * 0.8 <= price <= high * 1.2  # 20% tolerance
        confidence = 0.90 if match else 0.15
        return AttributeScore(
            attribute="price_band",
            match=match,
            confidence=confidence,
            evidence=f"Price {price} vs range {low}-{high}",
        )



def _check_audience(audience: str, category: str, title: str) -> AttributeScore | None:
    """
    Check if a product listing matches the requested audience gender.
    Returns None for gender-neutral categories — no check performed.
    """
    category_norm = " ".join(category.lower().split())
    # Skip check for gender-neutral categories
    if any(neutral in category_norm for neutral in GENDER_NEUTRAL_CATEGORIES):
        return None

    title_norm = _normalise(title)
    title_words = set(title_norm.split())

    is_male = bool(title_words & MALE_WORDS)
    is_female = bool(title_words & FEMALE_WORDS)
    is_unisex = 'unisex' in title_norm

    if is_unisex:
        return AttributeScore(
            attribute="audience", match=True, confidence=0.85,
            evidence="Unisex listing — suitable for all audiences",
        )
    if not is_male and not is_female:
        # No gender signal — listing is assumed compatible
        return AttributeScore(
            attribute="audience", match=True, confidence=0.70,
            evidence="No gender signal in listing — assumed compatible",
        )
    if audience == "male":
        if is_male:
            return AttributeScore(attribute="audience", match=True, confidence=0.95,
                evidence="Men's product confirmed in title")
        else:
            return AttributeScore(attribute="audience", match=False, confidence=0.10,
                evidence="Women's product; selected audience is Male")
    else:  # female
        if is_female:
            return AttributeScore(attribute="audience", match=True, confidence=0.95,
                evidence="Women's product confirmed in title")
        else:
            return AttributeScore(attribute="audience", match=False, confidence=0.10,
                evidence="Men's product; selected audience is Female")


def verify_match(item: ParsedItem, candidate: ProductCandidate, audience: str = "") -> VerificationResult:
    """
    Score a product candidate against a parsed item.

    Returns per-attribute scores and an overall confidence with honest labelling:
    - "Exact": brand + model both match
    - "Variant": brand matches but model differs or unspecified
    - "Best match to your description": generic item
    """
    scores: list[AttributeScore] = []

    # Always check category
    scores.append(_check_attribute("category", item.category, candidate.title))

    # Check optional attributes
    if item.colour:
        scores.append(_check_attribute("colour", item.colour, candidate.title))
    if item.brand:
        scores.append(_check_attribute("brand", item.brand, candidate.title))
    if item.model_name:
        scores.append(_check_attribute("model", item.model_name, candidate.title))
    if item.material:
        scores.append(_check_attribute("material", item.material, candidate.title))
    if item.fit_style:
        scores.append(_check_attribute("fit_style", item.fit_style, candidate.title))

    # Check audience match (skip for gender-neutral categories)
    if audience:
        audience_score = _check_audience(audience, item.category, candidate.title)
        if audience_score is not None:
            scores.append(audience_score)

    # Check price band
    if item.budget_hint and candidate.extracted_price is not None:
        scores.append(_check_price_band(item.budget_hint, candidate.extracted_price))

    # Calculate overall confidence (weighted: brand and model matter more for specific items)
    if not scores:
        overall = 0.5
    elif item.is_specific:
        # Weight brand and model higher for specific items
        weights = {"brand": 2.0, "model": 2.0}
        total_weight = sum(weights.get(s.attribute, 1.0) for s in scores)
        weighted_sum = sum(
            s.confidence * weights.get(s.attribute, 1.0) for s in scores
        )
        overall = weighted_sum / total_weight
    else:
        overall = sum(s.confidence for s in scores) / len(scores)

    # Determine honest label
    if item.is_specific:
        brand_ok = any(s.attribute == "brand" and s.match for s in scores)
        model_ok = any(s.attribute == "model" and s.match for s in scores)
        if brand_ok and model_ok:
            label = "Exact"
        elif brand_ok:
            label = "Variant"
        else:
            label = "Best match to your description"
    else:
        label = "Best match to your description"

    return VerificationResult(
        overall_confidence=round(overall, 3),
        scores=scores,
        label=label,
    )
