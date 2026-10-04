"""Tests for the product finder."""

import pytest
from app.finder import _build_shopping_params
from app.models import ParsedItem


class TestBuildShoppingParams:
    def test_india_market(self):
        item = ParsedItem(
            category="sneakers", colour="white", material="leather",
            is_specific=False, source_text="white leather sneakers",
            search_query="white leather sneakers"
        )
        params = _build_shopping_params(item, market="in")
        assert params["q"] == "white leather sneakers"
        assert params["gl"] == "in"
        assert params["hl"] == "en"
        assert params["google_domain"] == "google.co.in"

    def test_us_market(self):
        item = ParsedItem(
            category="sneakers", brand="Nike", model_name="Air Force 1",
            is_specific=True, source_text="Nike Air Force 1",
            search_query="Nike Air Force 1 sneakers"
        )
        params = _build_shopping_params(item, market="us")
        assert params["gl"] == "us"
        assert "google_domain" not in params

    def test_search_query_used_as_q(self):
        item = ParsedItem(
            category="chinos", colour="navy", fit_style="slim",
            is_specific=False, source_text="slim navy chinos",
            search_query="slim fit navy blue chinos men"
        )
        params = _build_shopping_params(item, market="in")
        assert params["q"] == "slim fit navy blue chinos men"
