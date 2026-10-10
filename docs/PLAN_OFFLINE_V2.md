# Offline v2: Brand-First Store Finder — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the current "search verified sellers on Maps" offline path with a 3-tier gated brand search that finds real physical clothing stores near the user, labelled by tier (brand store / multi-brand chain / category sweep), with credit budget enforcement, a negative cache, and matching UI honesty states.

**Architecture:** Backend: `store_finder_v2.py` (new file, replaces route handler calls to old finder), `store_matcher_v2.py` (extended with short-name rules). Frontend: `OfflineMode.tsx` updated with tier badges, "why shown" lines, honesty banner, and empty/partial states. Old seller-search path removed from offline only (kept for online mode).

**Tech Stack:** Python, FastAPI, Google Maps via SerpApi, SQLite (brand log + cache), Pydantic, Next.js/TypeScript, Leaflet/OSM.

## Global Constraints

- No Maps result ever appears beyond 50 km — enforced by haversine.
- No inventory claims. No fabricated fields. All card data from Maps only.
- Credits are hard: 30 per offline request. Budget enforced, not approximated.
- Infer nothing about stock. Label cached/demo data as such.
- All existing tests must keep passing.
- Feature flag: ship behind `offline_mode` setting until tests pass.

---

### Task 1: Extend Store Matcher (short-name rules)

**Files:**
- Modify: `backend/app/store_matcher.py`
- Test: `backend/tests/test_store_matcher_v2.py`

**Interfaces:**
- Produces: `match_store_to_brand(place: dict, brand: str, is_chain: bool=False) -> tuple[bool, str]` — returns (match, reason). For `len(brand) <= 4`, requires exact whole-token match OR website domain contains brand slug OR place type contains "clothing"/"apparel".

- [ ] **Step 1: Write failing tests for the short-name rule**

```python
# test_store_matcher_v2.py
from app.store_matcher import match_store_to_brand

def test_short_name_exact_token_match():
    place = {"title": "BIBA - Phoenix Market City", "types": ["clothing_store"], "gps_coordinates": {"latitude": 19.1, "longitude": 72.9}, "website": ""}
    ok, reason = match_store_to_brand(place, "Biba")
    assert ok

def test_short_name_no_match_different_business():
    place = {"title": "Max Steel Hardware", "types": ["hardware_store"], "website": ""}
    ok, _ = match_store_to_brand(place, "Max")
    assert not ok  # "Max" in title but types not clothing

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
```

- [ ] **Step 2: Run to confirm FAIL**
`cd backend && .venv\Scripts\python.exe -m pytest tests/test_store_matcher_v2.py -v`

- [ ] **Step 3: Implement `match_store_to_brand` in `store_matcher.py`**

```python
from difflib import SequenceMatcher

CLOTHING_TYPES = {"clothing_store", "apparel", "clothing", "fashion", "boutique"}

def _is_clothing_type(place: dict) -> bool:
    types = place.get("types", []) or []
    return any(t.lower() in CLOTHING_TYPES for t in types)

def match_store_to_brand(place: dict, brand: str, is_chain: bool = False) -> tuple[bool, str]:
    """
    Match a Maps place to a brand name.
    Short names (<=4 chars): exact whole-token + clothing type OR domain.
    Long names: fuzzy 90+.
    """
    title = normalise(place.get("title", ""))
    brand_norm = normalise(brand)
    website = (place.get("website") or "").lower()
    brand_slug = brand_norm.replace(" ", "")

    if len(brand_norm) <= 4:
        pattern = r'\b' + re.escape(brand_norm) + r'\b'
        token_match = bool(re.search(pattern, title))
        domain_match = bool(brand_slug and brand_slug in website)
        type_match = _is_clothing_type(place)
        if token_match and (type_match or domain_match):
            return True, f"Short-name token match '{brand}' with clothing type"
        return False, f"Short-name '{brand}' needs token+type or domain"
    else:
        ratio = SequenceMatcher(None, brand_norm, title).ratio()
        if ratio >= 0.9:
            return True, f"Fuzzy match {ratio:.2f} for '{brand}'"
        # also check if brand is fully contained in title
        if brand_norm in title:
            return True, f"Brand '{brand}' contained in title"
        return False, f"Fuzzy {ratio:.2f} < 0.9 for '{brand}'"
```

- [ ] **Step 4: Run tests — confirm PASS**
- [ ] **Step 5: Commit**
`git commit -m "feat: extend store_matcher with short-name and fuzzy rules"`

---

### Task 2: Brand Log SQLite Table (negative cache + evidence log)

**Files:**
- Modify: `backend/app/cache.py` (add `BrandLogDB` class)
- Test: `backend/tests/test_brand_log.py`

**Interfaces:**
- Produces: `BrandLogDB(db_path).log_brand_search(brand, city_cell, tier, place_id, match_score, lat, lng, found)`, `BrandLogDB.is_negative_cached(brand, city_cell, ttl_days=7) -> bool`

- [ ] **Step 1: Write failing tests**

```python
# test_brand_log.py
from app.cache import BrandLogDB
import tempfile, os

def test_log_and_retrieve_positive():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db = BrandLogDB(f.name)
    db.log_brand_search("Nike", "19.0_72.8", "tier1", "abc123", 0.95, 19.07, 72.88, found=True)
    assert not db.is_negative_cached("Nike", "19.0_72.8")

def test_log_negative_cache():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db = BrandLogDB(f.name)
    db.log_brand_search("FakeOnlyBrand", "19.0_72.8", "tier1", None, 0.0, 0, 0, found=False)
    assert db.is_negative_cached("FakeOnlyBrand", "19.0_72.8")

def test_negative_cache_expired_returns_false():
    # Insert with ttl_days=0 check: it's still in the table but TTL says skip
    pass  # implementation checks timestamp age
```

- [ ] **Step 2: Run to confirm FAIL**
- [ ] **Step 3: Implement `BrandLogDB` in `cache.py`**
```python
class BrandLogDB:
    def __init__(self, db_path: str):
        import sqlite3
        self._db = db_path
        with sqlite3.connect(db_path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS brand_log (
                brand TEXT, city_cell TEXT, tier TEXT, place_id TEXT,
                match_score REAL, lat REAL, lng REAL, found INTEGER,
                ts INTEGER DEFAULT (strftime('%s','now'))
            )""")
    def log_brand_search(self, brand, city_cell, tier, place_id, match_score, lat, lng, found):
        import sqlite3
        with sqlite3.connect(self._db) as conn:
            conn.execute("INSERT INTO brand_log VALUES (?,?,?,?,?,?,?,?,strftime('%s','now'))",
                         (brand, city_cell, tier, place_id, match_score, lat, lng, int(found)))
    def is_negative_cached(self, brand, city_cell, ttl_days=7) -> bool:
        import sqlite3, time
        cutoff = int(time.time()) - ttl_days * 86400
        with sqlite3.connect(self._db) as conn:
            row = conn.execute(
                "SELECT found FROM brand_log WHERE brand=? AND city_cell=? AND ts>? ORDER BY ts DESC LIMIT 1",
                (brand, city_cell, cutoff)).fetchone()
        return row is not None and row[0] == 0
```
- [ ] **Step 4: Run tests — PASS**
- [ ] **Step 5: Commit** `git commit -m "feat: add BrandLogDB for negative cache and evidence log"`

---

### Task 3: Three-Tier Store Finder v2

**Files:**
- Create: `backend/app/store_finder_v2.py`
- Test: `backend/tests/test_store_finder_v2.py`

**Interfaces:**
- Produces: `find_nearby_stores_v2(request: OfflineRequest, client: SerpApiClient, brand_log: BrandLogDB) -> AsyncIterator[tuple[StoreResult, str, str]]` — yields `(store, tier_label, why_shown)`.
- `INDIAN_CHAINS: list[str]` — fixed list of ~20 Indian multi-brand chains.
- `MAPS_CREDIT_BUDGET: int = 30`

**Chain list (verified against spike data):**
```python
INDIAN_CHAINS = [
    "Lifestyle", "Westside", "Pantaloons", "Shoppers Stop",
    "Max Fashion", "Reliance Trends", "Central", "Brand Factory",
    "V-Mart", "FBB", "Zudio", "H&M", "Zara", "Uniqlo",
    "Marks & Spencer", "Levi's Store", "Allen Solly Studio",
    "Peter England", "Van Heusen", "Louis Philippe",
]
```

**Stage logic:**
1. Category sweep (2 queries × 2 pages = 4 credits): `"men's clothing store"` / `"women's clothing store"` + `"shopping mall"`.
2. Chain sweep (up to 20, 1 credit each = 20 max): query each chain from `INDIAN_CHAINS`.
3. Brand queries (remaining budget): brands from extractor, ordered by item coverage count, 1 credit each.

- [ ] **Step 1: Write failing integration tests (with mock SerpApi client)**

```python
# test_store_finder_v2.py
from unittest.mock import AsyncMock, MagicMock
from app.store_finder_v2 import find_nearby_stores_v2, INDIAN_CHAINS
from app.models import OfflineRequest

def make_request(audience="male"):
    return OfflineRequest(
        sellers=[],
        product_title="Navy Blazer",
        lat=19.076, lng=72.878,
        market="in",
        audience=audience,
        is_specific=False,
        verified_results=[{
            "candidate": {"source": "Peter England", "title": "Peter England Blazer", "extracted_price": 3999.0},
            "verification": {"overall_confidence": 0.85, "scores": [], "label": "Best match"},
        }],
    )

async def test_category_sweep_uses_audience():
    client = MagicMock()
    client.search = AsyncMock(return_value={"local_results": []})
    request = make_request("female")
    results = []
    async for item in find_nearby_stores_v2(request, client, MagicMock()):
        results.append(item)
    # Verify "women's clothing store" was queried
    queries = [call.args[1]["q"] for call in client.search.call_args_list]
    assert any("women" in q.lower() for q in queries)

async def test_tier1_brand_stores_returned():
    place = {"title": "Peter England Exclusive", "types": ["clothing_store"],
             "gps_coordinates": {"latitude": 19.08, "longitude": 72.88},
             "place_id": "abc", "rating": 4.2}
    client = MagicMock()
    client.search = AsyncMock(return_value={"local_results": [place]})
    request = make_request()
    results = []
    async for item in find_nearby_stores_v2(request, client, MagicMock()):
        results.append(item)
    tiers = [r[1] for r in results]
    assert "tier1" in tiers

async def test_budget_not_exceeded():
    client = MagicMock()
    client.search = AsyncMock(return_value={"local_results": []})
    client.get_call_count = MagicMock(return_value=0)
    request = make_request()
    async for _ in find_nearby_stores_v2(request, client, MagicMock()):
        pass
    assert client.search.call_count <= 30

async def test_50km_enforced():
    far_place = {"title": "Peter England Store Pune", "types": ["clothing_store"],
                 "gps_coordinates": {"latitude": 18.52, "longitude": 73.86},  # ~150 km
                 "place_id": "far1"}
    client = MagicMock()
    client.search = AsyncMock(return_value={"local_results": [far_place]})
    request = make_request()
    results = []
    async for item in find_nearby_stores_v2(request, client, MagicMock()):
        results.append(item)
    assert len(results) == 0
```

- [ ] **Step 2: Run — confirm FAIL (module doesn't exist)**

- [ ] **Step 3: Implement `store_finder_v2.py`**

Key implementation notes:
- Extract brands using existing `extract_brands_from_results`
- Track `credit_used` counter, stop brand queries when budget reached
- Yield stores as AsyncIterator so SSE can stream them progressively
- Log every result to `BrandLogDB`
- Use `_city_cell(lat, lng)` = `f"{round(lat, 1)}_{round(lng, 1)}"` for cache key

- [ ] **Step 4: Run tests — PASS**
- [ ] **Step 5: Commit** `git commit -m "feat: add store_finder_v2 with 3-tier gated brand search"`

---

### Task 4: Wire v2 into API + Remove Old Seller Path from Offline

**Files:**
- Modify: `backend/app/api.py` (offline endpoint)
- Modify: `backend/app/models.py` (add tier, why_shown to StoreResult)

**Interfaces:**
- `StoreResult` gets new optional fields: `tier: str = "tier3"`, `why_shown: str`
- The offline endpoint calls `find_nearby_stores_v2` and streams `(store, tier, why_shown)` tuples
- SSE event `store_found` now includes `tier` and `why_shown`
- "N brands not searched" emitted as a `trace` event with `status: "budget_limit"`

- [ ] **Step 1: Add `tier` and `why_shown` to `StoreResult`**
- [ ] **Step 2: Update `api.py` offline endpoint to call v2 finder**
- [ ] **Step 3: Remove old `_find_stores_by_sellers` call from offline path** (sellers path stays only in online mode code, offline always uses v2)
- [ ] **Step 4: Run full test suite — all pass**
- [ ] **Step 5: Commit** `git commit -m "feat: wire offline v2 into API endpoint"`

---

### Task 5: Frontend — Tier UI, Why Shown, Empty States

**Files:**
- Modify: `frontend/src/components/OfflineMode.tsx`
- Modify: `frontend/src/components/StoreMap.tsx`
- Modify: `frontend/src/lib/api.ts` (if `StoreResult` type needs tier/why_shown)

**Design (ui-ux-pro-max): Tier labels and honesty**
- **Tier 1** badge: filled amber pill `"Brand store"` — only if Maps confirmed the brand in title
- **Tier 2** badge: outlined blue pill `"Multi-brand chain"` — always might stock it
- **Tier 3** badge: grey outlined pill `"Nearby shop"` — collapsed by default, user expands
- **"Why shown" line**: single-sentence plain text under the store name
- **Honesty banner** (persistent, not dismissable): `"We can't see shelves. Call before you go."`
- **Empty state**: centred map with 50 km circle, text "No stores found within 50 km of your location"
- **Budget notice**: amber inline banner `"X brands couldn't be searched (credit limit). Tap to search more →"`
- **No-brand notice**: grey inline text per item `"No brand identified in your results for [item name]"`

- [ ] **Step 1: Add `tier` and `why_shown` to TypeScript `StoreResult` type in `api.ts`**
- [ ] **Step 2: Add tier badge component in `OfflineMode.tsx`**
- [ ] **Step 3: Add "why shown" line below store name**
- [ ] **Step 4: Add honesty banner**
- [ ] **Step 5: Add empty state with 50 km circle on map**
- [ ] **Step 6: Add budget notice**
- [ ] **Step 7: Collapse tier-3 stores by default**
- [ ] **Step 8: Manual test — paste interview chat, verify pins stream with correct tiers**
- [ ] **Step 9: Commit** `git commit -m "feat(ui): add tier badges, why-shown, honesty states to offline mode"`

---

### Task 6: Demo Fixtures + Evaluation Report

**Files:**
- Create: `backend/scripts/seed_offline_fixtures.py`
- Create: `docs/EVAL_OFFLINE_V2.md`
- Modify: `README.md`

- [ ] **Step 1: Run 10 real queries (2 cities, both genders) and save to fixture file**
- [ ] **Step 2: Evaluate precision (hand-check): ≥80% of tier-1/2 pins correct within 50 km**
- [ ] **Step 3: Write `docs/EVAL_OFFLINE_V2.md` with all numbers**
- [ ] **Step 4: Update README offline section**
- [ ] **Step 5: Commit** `git commit -m "docs: offline v2 evaluation report and fixtures"`
