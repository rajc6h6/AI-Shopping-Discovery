"""Persistent SerpApi response cache backed by SQLite."""

import sqlite3
import json
import hashlib
from typing import Optional


class SerpApiCache:
    """Cache SerpApi responses keyed by normalised request (engine + sorted params)."""

    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                engine TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        self.conn.commit()

    def make_key(self, engine: str, params: dict) -> str:
        """Create a deterministic cache key from engine + sorted params."""
        # Remove api_key from params before hashing (never cache secrets)
        clean = {k: v for k, v in params.items() if k != "api_key"}
        normalised = json.dumps(
            {"engine": engine, **dict(sorted(clean.items()))}, sort_keys=True
        )
        return hashlib.sha256(normalised.encode()).hexdigest()

    def get(self, key: str) -> Optional[dict]:
        """Return cached response or None on miss."""
        row = self.conn.execute(
            "SELECT data FROM cache WHERE key = ?", (key,)
        ).fetchone()
        return json.loads(row[0]) if row else None

    def set(self, key: str, data: dict, engine: str = "") -> None:
        """Store a response in cache."""
        self.conn.execute(
            "INSERT OR REPLACE INTO cache (key, data, engine) VALUES (?, ?, ?)",
            (key, json.dumps(data), engine),
        )
        self.conn.commit()

    def count(self) -> int:
        """Return number of cached entries."""
        row = self.conn.execute("SELECT COUNT(*) FROM cache").fetchone()
        return row[0] if row else 0

    def close(self):
        self.conn.close()


class BrandLogDB:
    def __init__(self, db_path: str):
        self._db = db_path
        with sqlite3.connect(db_path, check_same_thread=False) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS brand_log (
                brand TEXT, city_cell TEXT, tier TEXT, place_id TEXT,
                match_score REAL, lat REAL, lng REAL, found INTEGER,
                ts INTEGER DEFAULT (strftime('%s','now'))
            )""")

    def log_brand_search(
        self, brand: str, city_cell: str, tier: str, place_id: Optional[str],
        match_score: float, lat: float, lng: float, found: bool
    ):
        with sqlite3.connect(self._db) as conn:
            conn.execute(
                "INSERT INTO brand_log VALUES (?,?,?,?,?,?,?,?,strftime('%s','now'))",
                (brand, city_cell, tier, place_id, match_score, lat, lng, int(found))
            )

    def is_negative_cached(self, brand: str, city_cell: str, ttl_days: int = 7) -> bool:
        import time
        cutoff = int(time.time()) - ttl_days * 86400
        with sqlite3.connect(self._db) as conn:
            row = conn.execute(
                "SELECT found FROM brand_log WHERE brand=? AND city_cell=? AND ts>? ORDER BY ts DESC LIMIT 1",
                (brand, city_cell, cutoff)
            ).fetchone()
        return row is not None and row[0] == 0
