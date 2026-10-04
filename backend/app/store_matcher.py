"""Seller-to-store matching: verifies a Maps place genuinely belongs to a verified seller.

Uses word-boundary matching on title + domain matching on website to avoid false positives.
"""

import re


def normalise(name: str) -> str:
    """Lowercase, strip common suffixes like 'India', 'Store', 'Official'."""
    name = name.lower().strip()
    for noise in ['india', 'store', 'official', 'retail', 'outlet',
                  'pvt', 'ltd', 'private', 'limited', 'inc', 'llc',
                  '.com', '.in', '.co']:
        name = re.sub(rf'\b{re.escape(noise)}\b', '', name)
    return re.sub(r'\s+', ' ', name).strip()


def match_store_to_seller(
    store_data: dict,
    seller_name: str,
) -> tuple[bool, str]:
    """
    Check if a Google Maps place genuinely belongs to the given seller.

    Returns (is_match, reason_string).

    Matching criteria (must satisfy at least one):
    1. Store title contains the seller name at a word boundary
    2. Store website domain contains seller name

    Anti-false-positive: word-boundary matching prevents "Chroma Art" matching "Croma".
    """
    store_title = normalise(store_data.get('title', ''))
    seller_norm = normalise(seller_name)

    if not seller_norm or len(seller_norm) < 2:
        return False, f"Seller name '{seller_name}' too short to match"

    # Check 1: Title contains seller name at word boundary
    pattern = r'\b' + re.escape(seller_norm) + r'\b'
    if re.search(pattern, store_title):
        return True, f"Title '{store_data['title']}' matches seller '{seller_name}'"

    # Check 2: Website domain matches
    website = store_data.get('website', '') or ''
    seller_slug = seller_norm.replace(' ', '')
    if website and seller_slug and seller_slug in website.lower():
        return True, f"Website '{website[:60]}' matches seller '{seller_name}'"

    return False, f"No match: '{store_data.get('title', '')}' ≠ '{seller_name}'"
