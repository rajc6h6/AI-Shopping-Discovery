"""Thin SerpApi HTTP client with caching, call cap, and tracing."""

import httpx
from typing import Any
from app.cache import SerpApiCache


class CallCapExceeded(Exception):
    """Raised when the session call cap is reached."""
    pass


class SerpApiError(Exception):
    """Raised on SerpApi HTTP or response errors."""
    pass


class SerpApiClient:
    """
    Async SerpApi client.

    - Caches every response by normalised request key.
    - Tracks call count per session, raises CallCapExceeded at cap.
    - Logs every call (engine, params, cached flag) for the trace panel.
    """

    BASE_URL = "https://serpapi.com/search.json"

    def __init__(
        self,
        api_key: str,
        cache_db: str,
        max_calls: int = 50,
        demo_mode: bool = False,
    ):
        self.api_key = api_key
        self.cache = SerpApiCache(cache_db)
        self.max_calls = max_calls
        self.demo_mode = demo_mode
        self._call_count = 0
        self._call_log: list[dict] = []

    def _check_cap(self):
        if self._call_count >= self.max_calls:
            raise CallCapExceeded(
                f"Session cap of {self.max_calls} SerpApi calls reached"
            )

    async def search(self, engine: str, params: dict) -> dict:
        """
        Search SerpApi. Returns cached result if available,
        otherwise makes a live call and caches it.
        """
        key = self.cache.make_key(engine, params)

        # Check cache first
        cached = self.cache.get(key)
        if cached is not None:
            self._call_log.append({
                "engine": engine,
                "params": {k: v for k, v in params.items() if k != "api_key"},
                "cached": True,
                "status": "hit",
            })
            return cached

        # Demo mode: never make live calls — only serve from cache
        if self.demo_mode:
            raise SerpApiError(
                f"[demo] No cached result for engine={engine}. "
                "Run scripts/cache_demo_data.py to pre-populate demo cache."
            )

        # Check call cap before making live request
        self._check_cap()

        # Make live request
        full_params = {
            **params,
            "engine": engine,
            "api_key": self.api_key,
            "output": "json",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(self.BASE_URL, params=full_params)

                if resp.status_code == 429:
                    raise SerpApiError("SerpApi rate limit reached. Try again later.")

                resp.raise_for_status()
                data = resp.json()
        except httpx.TimeoutException:
            raise SerpApiError(f"SerpApi request timed out for engine={engine}")
        except httpx.HTTPStatusError as e:
            raise SerpApiError(f"SerpApi HTTP error {e.response.status_code}: {e.response.text[:200]}")

        # Check for API-level errors
        if "error" in data:
            raise SerpApiError(f"SerpApi error: {data['error']}")

        # Cache and track
        self.cache.set(key, data, engine=engine)
        self._call_count += 1
        self._call_log.append({
            "engine": engine,
            "params": {k: v for k, v in params.items() if k != "api_key"},
            "cached": False,
            "status": "live",
        })
        return data

    def get_call_log(self) -> list[dict]:
        """Return the full call log for this session."""
        return self._call_log

    def get_call_count(self) -> int:
        """Return the number of live (non-cached) calls made."""
        return self._call_count
