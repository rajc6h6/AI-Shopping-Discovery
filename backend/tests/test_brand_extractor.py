"""Tests for the brand extractor module."""

import pytest
from app.brand_extractor import extract_brands_from_results, MARKETPLACE_SELLERS


def _r(source: str, title: str, conf: float) -> dict:
    return {
        "candidate": {"source": source, "title": title, "extracted_price": 2000.0},
        "verification": {"overall_confidence": conf, "scores": [], "label": "Best match"},
    }


class TestExtractBrandsFromResults:
    def test_extracts_brand_from_source(self):
        results = [
            _r("Nike", "Nike Air Force 1 Sneakers", 0.85),
            _r("Nike", "Nike Pegasus Running Shoes", 0.75),
            _r("Adidas", "Adidas Ultraboost 22", 0.70),
        ]
        brands = extract_brands_from_results(results, "male")
        assert "Nike" in brands
        assert "Adidas" in brands

    def test_excludes_marketplace_amazon(self):
        results = [
            _r("Amazon", "Nike Men Sneakers", 0.90),
            _r("Puma", "Puma RS-X Sneakers", 0.80),
        ]
        brands = extract_brands_from_results(results, "male")
        assert "Amazon" not in brands
        assert "Puma" in brands

    def test_marketplace_source_extracts_from_title(self):
        """When source is a marketplace, brand is extracted from title instead."""
        results = [_r("Flipkart", "Adidas Shoes Men", 0.85)]
        brands = extract_brands_from_results(results, "male")
        # Flipkart is a marketplace; brand extracted from title
        assert "Flipkart" not in brands
        assert "Adidas" in brands

    def test_excludes_low_confidence_candidates(self):
        results = [_r("Nike", "Nike Shoes", 0.3)]  # below min_confidence=0.5
        brands = extract_brands_from_results(results, "male")
        assert brands == []

    def test_single_brand_above_single_threshold(self):
        """Single occurrence above 0.6 is included."""
        results = [_r("Woodland", "Woodland Men Boots", 0.82)]
        brands = extract_brands_from_results(results, "male")
        assert "Woodland" in brands

    def test_single_brand_below_single_threshold(self):
        """Single occurrence below 0.6 is excluded (min_single_confidence=0.6)."""
        results = [_r("Woodland", "Woodland Men Boots", 0.55)]
        brands = extract_brands_from_results(results, "male")
        assert brands == []

    def test_caps_at_three_brands(self):
        results = [
            _r(b, f"{b} Shoes Men", 0.8) for b in ["Nike", "Adidas", "Puma", "Reebok", "Fila"]
        ]
        brands = extract_brands_from_results(results, "male")
        assert len(brands) <= 3

    def test_deterministic_same_input_same_output(self):
        results = [
            _r("Nike", "Nike Shoes", 0.85),
            _r("Adidas", "Adidas Shoes", 0.80),
        ]
        assert (
            extract_brands_from_results(results, "male")
            == extract_brands_from_results(results, "male")
        )

    def test_marketplace_source_no_brand_in_title(self):
        """When all sources are marketplaces AND no brand can be extracted from titles."""
        results = [
            _r("Amazon", "Casual Sports Running Shoes", 0.90),  # no brand token
            _r("Flipkart", "Men Sports Shoes", 0.80),           # no brand token
        ]
        brands = extract_brands_from_results(results, "male")
        assert "Amazon" not in brands
        assert "Flipkart" not in brands

    def test_returns_empty_when_all_low_confidence(self):
        results = [
            _r("Nike", "Nike Shoes", 0.45),  # below min_confidence
            _r("Adidas", "Adidas Shoes", 0.48),
        ]
        assert extract_brands_from_results(results, "male") == []

    def test_multiple_occurrences_boost_rank(self):
        """Brand with more occurrences should rank higher than brand with one."""
        results = [
            _r("Nike", "Nike Shoes", 0.85),
            _r("Nike", "Nike Sneakers", 0.80),  # 2 occurrences: score = 1.65
            _r("Adidas", "Adidas Shoes", 0.90),  # 1 occurrence: score = 0.90
        ]
        brands = extract_brands_from_results(results, "male")
        assert brands[0] == "Nike"  # higher total confidence

    def test_top_3_by_score_not_count(self):
        """Test that scoring is by confidence sum, not count."""
        results = [
            _r("Nike", "Nike A", 0.90),
            _r("Nike", "Nike B", 0.88),  # Nike total = 1.78
            _r("Adidas", "Adidas A", 0.95),
            _r("Adidas", "Adidas B", 0.93),  # Adidas total = 1.88
            _r("Puma", "Puma A", 0.75),
        ]
        brands = extract_brands_from_results(results, "male")
        assert brands[0] == "Adidas"  # highest total
        assert brands[1] == "Nike"


class TestMarketplaceSellersSet:
    def test_contains_common_marketplaces(self):
        for m in ["amazon", "flipkart", "myntra", "ebay", "ajio", "meesho"]:
            assert m in MARKETPLACE_SELLERS

    def test_does_not_contain_brand_names(self):
        for b in ["nike", "adidas", "puma", "zara", "h&m"]:
            assert b not in MARKETPLACE_SELLERS
