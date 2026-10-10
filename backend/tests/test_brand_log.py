from app.cache import BrandLogDB
import tempfile
import os
import time

def test_log_and_retrieve_positive():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        db = BrandLogDB(db_path)
        db.log_brand_search("Nike", "19.0_72.8", "tier1", "abc123", 0.95, 19.07, 72.88, found=True)
        assert not db.is_negative_cached("Nike", "19.0_72.8")
    finally:
        os.remove(db_path)

def test_log_negative_cache():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        db = BrandLogDB(db_path)
        db.log_brand_search("FakeOnlyBrand", "19.0_72.8", "tier1", None, 0.0, 0, 0, found=False)
        assert db.is_negative_cached("FakeOnlyBrand", "19.0_72.8")
    finally:
        os.remove(db_path)

def test_negative_cache_expired_returns_false():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        db = BrandLogDB(db_path)
        # Log manually with old timestamp
        import sqlite3
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "INSERT INTO brand_log (brand, city_cell, found, ts) VALUES (?, ?, ?, ?)",
                ("ExpiredBrand", "19.0_72.8", 0, int(time.time()) - 8 * 86400)
            )
        assert not db.is_negative_cached("ExpiredBrand", "19.0_72.8", ttl_days=7)
    finally:
        os.remove(db_path)
