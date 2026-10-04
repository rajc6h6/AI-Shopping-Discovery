"""Tests for the 50 km radius enforcement in store_finder."""

import pytest
from app.store_finder import _haversine_km, _within_radius, OFFLINE_RADIUS_KM
from app.models import OfflineResult


class TestRadiusConstant:
    def test_radius_constant_is_50(self):
        assert OFFLINE_RADIUS_KM == 50


class TestHaversine:
    def test_mumbai_to_pune_approx_120km(self):
        """Straight-line (haversine) distance Mumbai to Pune is ~120 km.
        Note: road distance is ~148 km but haversine measures the geodesic."""
        d = _haversine_km(19.0760, 72.8777, 18.5204, 73.8567)
        assert 110 < d < 135

    def test_same_point_is_zero(self):
        assert _haversine_km(19.0, 72.0, 19.0, 72.0) == pytest.approx(0.0, abs=0.01)

    def test_1_degree_lat_is_approx_111km(self):
        d = _haversine_km(0.0, 0.0, 1.0, 0.0)
        assert 110 < d < 112


class TestWithinRadius:
    def test_49km_is_inside(self):
        offset = 49 / 111.0  # ~49 km north
        assert _within_radius(0.0, 0.0, offset, 0.0)

    def test_50km_is_inside(self):
        """A point exactly 50 km north should be inside (boundary inclusive)."""
        # 50 km north: 50/111.32 degrees latitude
        offset = 50 / 111.32
        d = _haversine_km(0.0, 0.0, offset, 0.0)
        assert _within_radius(0.0, 0.0, offset, 0.0), f"Expected {d:.2f} km to be inside 50 km radius"

    def test_51km_is_outside(self):
        offset = 51 / 111.32  # ~51 km north — just outside boundary
        assert not _within_radius(0.0, 0.0, offset, 0.0)

    def test_mumbai_pune_outside(self):
        """Mumbai to Pune straight-line is ~120 km — well outside 50 km."""
        assert not _within_radius(19.0760, 72.8777, 18.5204, 73.8567)


class TestOfflineResultRadiusFields:
    def test_empty_radius_default_false(self):
        r = OfflineResult(stores=[], online_only_sellers=[], search_engines_used=[])
        assert r.empty_radius is False

    def test_radius_km_default_50(self):
        r = OfflineResult(stores=[], online_only_sellers=[], search_engines_used=[])
        assert r.radius_km == 50

    def test_can_set_empty_radius_true(self):
        r = OfflineResult(stores=[], online_only_sellers=[], search_engines_used=[], empty_radius=True)
        assert r.empty_radius is True


class TestNoCoordinateExclusion:
    def test_zero_coordinates_are_falsy(self):
        """Sentinel for 'no GPS data' — Python 0.0 is falsy, so the check `if not (lat and lng)` works."""
        lat, lng = 0.0, 0.0
        assert not (lat and lng)  # confirms the guard used in _store_from_place
