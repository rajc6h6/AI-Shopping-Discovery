"""Tests for audience propagation in verifier and finder."""

import pytest
from app.verifier import verify_match, _check_audience
from app.finder import _build_shopping_params
from app.models import ParsedItem, ProductCandidate


def _item(category="blazer", query="navy blazer"):
    return ParsedItem(
        category=category,
        is_specific=False,
        source_text="test",
        search_query=query,
    )


def _candidate(title):
    return ProductCandidate(
        title=title,
        source="TestSeller",
        link="http://x.com",
        engine_used="google_shopping",
        position=1,
        currency="INR",
    )


class TestVerifierAudience:
    def test_penalises_wrong_audience_male(self):
        result = verify_match(_item("blazer"), _candidate("Women's Navy Blazer Formal"), audience="male")
        score = next(s for s in result.scores if s.attribute == "audience")
        assert not score.match
        assert score.confidence < 0.3

    def test_penalises_wrong_audience_female(self):
        result = verify_match(_item("blazer"), _candidate("Men's Navy Slim Fit Blazer"), audience="female")
        score = next(s for s in result.scores if s.attribute == "audience")
        assert not score.match
        assert score.confidence < 0.3

    def test_passes_correct_audience_male(self):
        result = verify_match(_item("blazer"), _candidate("Men's Navy Slim Fit Blazer"), audience="male")
        score = next(s for s in result.scores if s.attribute == "audience")
        assert score.match
        assert score.confidence > 0.8

    def test_passes_correct_audience_female(self):
        result = verify_match(_item("blazer"), _candidate("Women's Navy Blazer"), audience="female")
        score = next(s for s in result.scores if s.attribute == "audience")
        assert score.match
        assert score.confidence > 0.8

    def test_skips_audience_for_neutral_category_laptop(self):
        result = verify_match(_item("laptop"), _candidate("Women's Laptop Bag 15 inch"), audience="male")
        assert not any(s.attribute == "audience" for s in result.scores)

    def test_skips_audience_for_neutral_category_watch(self):
        result = verify_match(_item("watch"), _candidate("Women's Gold Watch"), audience="male")
        assert not any(s.attribute == "audience" for s in result.scores)

    def test_passes_unisex_listing(self):
        result = verify_match(_item("sneakers"), _candidate("Unisex White Running Shoes"), audience="male")
        score = next(s for s in result.scores if s.attribute == "audience")
        assert score.match

    def test_no_gender_signal_assumed_compatible(self):
        result = verify_match(_item("blazer"), _candidate("Navy Slim Blazer Classic"), audience="male")
        score = next(s for s in result.scores if s.attribute == "audience")
        assert score.match
        assert score.confidence == 0.70

    def test_no_audience_skips_check(self):
        """When audience is empty string, no audience score is added."""
        result = verify_match(_item("blazer"), _candidate("Women's Navy Blazer"), audience="")
        assert not any(s.attribute == "audience" for s in result.scores)

    def test_overall_confidence_penalised_for_wrong_gender(self):
        """Wrong gender should lower overall confidence below no-gender-signal baseline."""
        result_wrong = verify_match(_item("blazer"), _candidate("Women's Blazer"), audience="male")
        result_ok = verify_match(_item("blazer"), _candidate("Men's Blazer"), audience="male")
        assert result_ok.overall_confidence > result_wrong.overall_confidence


class TestFinderAudienceInjection:
    def test_injects_men_when_missing(self):
        item = _item("blazer", "navy blazer")
        params = _build_shopping_params(item, market="in", audience="male")
        assert "men" in params["q"].lower()

    def test_injects_women_when_missing(self):
        item = _item("blazer", "navy blazer")
        params = _build_shopping_params(item, market="in", audience="female")
        assert "women" in params["q"].lower()

    def test_no_duplicate_audience_word(self):
        item = _item("blazer", "men navy slim blazer")
        params = _build_shopping_params(item, market="in", audience="male")
        assert params["q"].lower().count("men") == 1

    def test_skips_injection_for_neutral_laptop(self):
        item = _item("laptop", "laptop 15 inch")
        params = _build_shopping_params(item, market="in", audience="male")
        assert "men" not in params["q"].lower()

    def test_skips_injection_for_neutral_watch(self):
        item = _item("watch", "smartwatch android")
        params = _build_shopping_params(item, market="in", audience="female")
        assert "women" not in params["q"].lower()

    def test_no_audience_unchanged_query(self):
        item = _item("blazer", "navy blazer")
        params = _build_shopping_params(item, market="in", audience="")
        assert params["q"] == "navy blazer"
