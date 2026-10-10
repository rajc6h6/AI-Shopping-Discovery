"""Tests for extended short-name and fuzzy matching rules in v2 store matcher."""
from app.store_matcher import match_store_to_brand

def test_short_name_exact_token_match():
    place = {"title": "BIBA - Phoenix Market City", "types": ["clothing_store"], "gps_coordinates": {"latitude": 19.1, "longitude": 72.9}, "website": ""}
    ok, reason = match_store_to_brand(place, "Biba")
    assert ok

def test_short_name_no_match_different_business():
    place = {"title": "Max Steel Hardware", "types": ["hardware_store"], "website": ""}
    ok, _ = match_store_to_brand(place, "Max")
    assert not ok

def test_short_name_clothing_type_override():
    place = {"title": "Max Fashion", "types": ["clothing_store"], "website": ""}
    ok, _ = match_store_to_brand(place, "Max")
    assert ok

def test_long_name_fuzzy_90():
    place = {"title": "Peter England Exclusive Store", "types": ["clothing_store"], "website": ""}
    ok, _ = match_store_to_brand(place, "Peter England")
    assert ok

def test_long_name_below_90():
    place = {"title": "Peter Exeter Clothing", "types": ["clothing_store"], "website": ""}
    ok, _ = match_store_to_brand(place, "Peter England")
    assert not ok
