"""Tests for the confidence verifier."""

import pytest
from app.verifier import verify_match, _check_attribute
from app.models import ParsedItem, ProductCandidate


class TestCheckAttribute:
    def test_none_expected_always_matches(self):
        result = _check_attribute("colour", None, "Any Product Title")
        assert result.match is True
        assert result.confidence == 1.0

    def test_direct_match(self):
        result = _check_attribute("colour", "white", "White Leather Sneakers")
        assert result.match is True
        assert result.confidence >= 0.9

    def test_synonym_match(self):
        result = _check_attribute("colour", "navy", "Dark Blue Slim Chinos")
        assert result.match is True
        assert result.confidence >= 0.7

    def test_no_match(self):
        result = _check_attribute("colour", "red", "Blue Cotton T-Shirt")
        assert result.match is False
        assert result.confidence < 0.3

    def test_category_sneakers_matches_shoes(self):
        result = _check_attribute("category", "sneakers", "Running Shoes White")
        assert result.match is True

    def test_brand_case_insensitive(self):
        result = _check_attribute("brand", "Nike", "nike air force 1 white")
        assert result.match is True


class TestVerifyMatch:
    def test_exact_brand_and_model(self):
        item = ParsedItem(
            category="sneakers", brand="Nike", model_name="Air Force 1",
            is_specific=True, source_text="Nike Air Force 1",
            search_query="Nike Air Force 1"
        )
        candidate = ProductCandidate(
            title="Nike Air Force 1 '07 White Sneakers",
            price="$110", extracted_price=110.0, currency="USD",
            source="Nike.com", link="https://nike.com/af1",
            engine_used="google_shopping", position=1
        )
        result = verify_match(item, candidate)
        assert result.label == "Exact"
        assert result.overall_confidence >= 0.8

    def test_variant_brand_only(self):
        item = ParsedItem(
            category="sneakers", brand="Nike", model_name="Air Force 1",
            is_specific=True, source_text="Nike Air Force 1",
            search_query="Nike Air Force 1"
        )
        candidate = ProductCandidate(
            title="Nike Dunk Low White Sneakers",
            price="$100", extracted_price=100.0, currency="USD",
            source="Foot Locker", link="https://footlocker.com/...",
            engine_used="google_shopping", position=3
        )
        result = verify_match(item, candidate)
        assert result.label == "Variant"

    def test_generic_item_best_match(self):
        item = ParsedItem(
            category="sneakers", colour="white", material="leather",
            is_specific=False, source_text="white leather sneakers",
            search_query="white leather sneakers"
        )
        candidate = ProductCandidate(
            title="Adidas Stan Smith White Leather Sneaker",
            price="$85", extracted_price=85.0, currency="USD",
            source="Amazon", link="https://amazon.com/...",
            engine_used="google_shopping", position=1
        )
        result = verify_match(item, candidate)
        assert result.label == "Best match to your description"
        assert result.overall_confidence > 0.5

    def test_poor_match_low_confidence(self):
        item = ParsedItem(
            category="chinos", colour="navy", fit_style="slim",
            is_specific=False, source_text="slim navy chinos",
            search_query="slim navy chinos"
        )
        candidate = ProductCandidate(
            title="Red Cargo Pants Wide Leg Baggy",
            price="$40", extracted_price=40.0, currency="USD",
            source="Shein", link="https://shein.com/...",
            engine_used="google_shopping", position=8
        )
        result = verify_match(item, candidate)
        assert result.overall_confidence < 0.5

    def test_scores_breakdown_present(self):
        item = ParsedItem(
            category="sneakers", colour="white", brand="Nike",
            is_specific=False, source_text="white Nike sneakers",
            search_query="white Nike sneakers"
        )
        candidate = ProductCandidate(
            title="Nike White Running Shoes",
            price="$90", extracted_price=90.0, currency="USD",
            source="Nike.com", link="https://...",
            engine_used="google_shopping", position=1
        )
        result = verify_match(item, candidate)
        attrs = [s.attribute for s in result.scores]
        assert "category" in attrs
        assert "colour" in attrs
        assert "brand" in attrs
        # Each score has evidence
        for score in result.scores:
            assert score.evidence != ""
