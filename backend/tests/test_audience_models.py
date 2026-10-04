"""Tests for audience-related model validation."""

from pydantic import ValidationError
import pytest
from app.models import SearchRequest, CompareRequest, OfflineRequest, OfflineResult


class TestSearchRequestAudience:
    def test_requires_audience(self):
        with pytest.raises(ValidationError):
            SearchRequest(chat_text="test", market="in")

    def test_rejects_invalid_audience(self):
        with pytest.raises(ValidationError):
            SearchRequest(chat_text="test", market="in", audience="unisex")

    def test_accepts_male(self):
        req = SearchRequest(chat_text="test", market="in", audience="male")
        assert req.audience == "male"

    def test_accepts_female(self):
        req = SearchRequest(chat_text="test", market="in", audience="female")
        assert req.audience == "female"


class TestCompareRequestAudience:
    def test_requires_audience(self):
        with pytest.raises(ValidationError):
            CompareRequest(product_title="t", product_attributes={}, market="in")

    def test_accepts_male(self):
        req = CompareRequest(product_title="t", product_attributes={}, market="in", audience="male")
        assert req.audience == "male"


class TestOfflineRequestAudience:
    def test_requires_audience(self):
        with pytest.raises(ValidationError):
            OfflineRequest(sellers=[], product_title="t", lat=0.0, lng=0.0, market="in")

    def test_accepts_female(self):
        req = OfflineRequest(sellers=[], product_title="t", lat=0.0, lng=0.0, market="in", audience="female")
        assert req.audience == "female"

    def test_is_specific_defaults_false(self):
        req = OfflineRequest(sellers=[], product_title="t", lat=0.0, lng=0.0, market="in", audience="male")
        assert req.is_specific is False

    def test_verified_results_defaults_empty(self):
        req = OfflineRequest(sellers=[], product_title="t", lat=0.0, lng=0.0, market="in", audience="male")
        assert req.verified_results == []


class TestOfflineResultFields:
    def test_empty_radius_defaults_false(self):
        r = OfflineResult(stores=[], online_only_sellers=[], search_engines_used=[])
        assert r.empty_radius is False

    def test_radius_km_defaults_50(self):
        r = OfflineResult(stores=[], online_only_sellers=[], search_engines_used=[])
        assert r.radius_km == 50

    def test_brand_source_note_defaults_none(self):
        r = OfflineResult(stores=[], online_only_sellers=[], search_engines_used=[])
        assert r.brand_source_note is None
