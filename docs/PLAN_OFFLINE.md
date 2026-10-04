# Offline Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an Online/Offline toggle to the product results. "Offline" finds nearby physical stores of verified online sellers using SerpApi Google Maps, shows them on an interactive map with store cards, evidence lines, and Call/Directions actions.

**Architecture:** New `store_finder.py` backend agent queries SerpApi `google_maps` engine per verified seller near user's location. Results stream via existing SSE pattern as `store_found` events. Frontend adds a toggle, Leaflet.js map (free, no API key), and synced store card list. All behind a feature flag `OFFLINE_MODE=true`.

**Tech Stack:**
- Backend: Existing FastAPI + httpx + SQLite cache. New `store_finder.py`, `store_matcher.py`, extended `api.py`
- Frontend: Leaflet.js + react-leaflet (free, no API key), OpenStreetMap tiles
- Map choice reasoning: Leaflet + OSM is the only option that works without paid API keys, has excellent mobile support, and is production-grade

## Global Constraints

- Reuse existing `SerpApiClient`, `SerpApiCache`, SSE pattern, trace system, CSS design system
- Offline mode budget: max 5 sellers searched per product, max 1 Maps call per seller = max 5 SerpApi calls per offline run
- Total session cap remains 50 (offline calls count against it)
- Cache key for Maps: SHA-256 of `{engine: "google_maps", q: "<seller>", ll: "<rounded_lat>,<rounded_lng>"}` — location rounded to 2 decimal places (~1km)
- Never claim stock availability. Evidence-based wording only.
- Feature flag: `OFFLINE_MODE` env var, default `true`

## Verified SerpApi Google Maps Fields (from live test)

```
engine: google_maps
params: q, ll (@lat,lng,zoomz), type=search

Returns per result:
  title, place_id, data_id, gps_coordinates {lat, lng},
  rating, reviews, type, types[], address, country,
  phone, website, thumbnail, open_state, hours,
  operating_hours {monday..sunday}, reviews_link, photos_link
```

All fields confirmed present for Indian retailers (tested: Croma stores in Mumbai — 20 results, with phone, hours, website, rating, reviews, coordinates).

---

### Task 1: Backend — Store Finder Data Models

**Files:**
- Modify: `backend/app/models.py` — add `StoreResult`, `OfflineRequest`, `OfflineResult`
- Modify: `backend/app/config.py` — add `offline_mode` and `max_calls_per_offline` settings

**Interfaces:**
- Produces: `StoreResult`, `OfflineRequest`, `OfflineResult` pydantic models
- Produces: `offline_mode: bool`, `max_calls_per_offline: int` config fields

---

### Task 2: Backend — Store Finder Agent + Seller Matcher

**Files:**
- Create: `backend/app/store_finder.py`
- Create: `backend/app/store_matcher.py`

**Interfaces:**
- Consumes: `SerpApiClient.search()`, `OfflineRequest`
- Produces: `find_nearby_stores(request, client) -> OfflineResult`
- Produces: `match_store_to_seller(store_data, seller_name) -> (bool, reason)`

---

### Task 3: Backend — Offline API Endpoint

**Files:**
- Modify: `backend/app/api.py` — add `POST /api/offline` SSE endpoint

**Interfaces:**
- SSE events: `trace` (agent: "offline"), `store_found`, `offline_complete`, `error`

---

### Task 4: Frontend — API Client + Types

**Files:**
- Modify: `frontend/src/lib/api.ts` — add `StoreResult`, `OfflineResult` types and `streamOffline()`

---

### Task 5: Frontend — Toggle + Map + Store Cards

**Files:**
- Create: `frontend/src/components/OfflineMode.tsx`
- Create: `frontend/src/components/StoreMap.tsx`
- Create: `frontend/src/components/OfflineMode.module.css`
- Modify: `frontend/src/app/PasteToProductClient.tsx`

---

### Task 6: Demo Cache + Docs

**Files:**
- Create: `backend/scripts/cache_offline_demo.py`
- Modify: `docs/SERPAPI_NOTES.md`, `docs/DECISIONS.md`, `docs/SKILLS_USED.md`

---

## Key Decisions

| # | Decision | Choice | Reason |
|---|----------|--------|--------|
| D14 | Map technology | Leaflet.js + OpenStreetMap tiles | Free (no API key), MIT licensed, excellent mobile, 40KB gzipped. Google Maps requires paid key. |
| D15 | Seller-to-store matching | Title word-boundary match + website domain match | Simple, deterministic, testable. Rejects false positives. |
| D16 | Offline SerpApi budget | 5 calls max per offline run | Stays within 50-call session cap. Cached aggressively. |
| D17 | Location privacy | Browser geolocation, rounded to 2dp in cache keys | Minimal data, clear copy. Manual fallback for denied. |
| D18 | Online-only detection | Known list + evidence-based | Hard-coded for obvious (Amazon etc), Maps evidence for unknowns. |
