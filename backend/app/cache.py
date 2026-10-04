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
