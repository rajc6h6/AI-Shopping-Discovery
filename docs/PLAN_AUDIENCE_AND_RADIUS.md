# Audience Selector & 50 km Radius — Architecture Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement the tasks in `docs/superpowers/plans/2026-10-03-audience-brand-radius.md`.

**Goal:** Add a mandatory Male/Female audience selector that threads through the entire pipeline, and enforce a strict 50 km radius in Offline mode with an empty-map honest state when nothing is found.

**Architecture:** Audience is a validated enum `Literal["male", "female"]` added to every request model. It flows from the frontend selector → backend request body → parser prompt injection → SerpApi queries → verifier attribute → compare agent → offline store queries → cache keys. The 50 km radius is enforced in-code using the existing haversine function after Maps results arrive, with a named constant `OFFLINE_RADIUS_KM = 50`.

**Tech Stack:** Python/FastAPI backend (Pydantic models, existing cache), Next.js/React frontend (existing design system), Leaflet.js (already installed for the map circle).

---

## Gender Flow Through the Pipeline

```
User selects Male/Female (frontend)
    ↓ audience: "male" | "female"
POST /api/search {chat_text, market, audience}   ← backend validates, rejects missing
    ↓
parse_chat(text, key, audience=audience)
    ↓  system prompt includes: "Every item is for {audience}. gender field = '{audience}'."
LLM response: all items have gender = audience
    ↓
find_products(item, client, market, audience)
    ↓  search_query already includes gender word (from prompt); finder adds it if missing
SerpApi Google Shopping results
    ↓
verify_match(item, candidate, audience)
    ↓  new attribute: "audience" checked against candidate title
        - "men" / "women" title word → match/mismatch → penalise wrong gender
        - Gender-neutral categories (phone, bag, watch) → skip audience check
VerificationResult.scores includes audience AttributeScore
    ↓
compare_prices(..., audience=audience)
    ↓  queries include audience; verify_match receives it
POST /api/offline {sellers, ..., audience}
    ↓
find_nearby_stores(request) → brand queries include audience
```

### Gender-Neutral Category List (no audience penalty in verifier)
Categories where audience check is skipped:
`phone, smartphone, laptop, tablet, watch, bag, backpack, wallet, sunglasses, belt, hat, cap, water bottle, earphones, headphones, perfume, fragrance, jewellery, jewelry`

**Decision**: Watches and sunglasses are borderline; included in neutral because gender words rarely appear in titles and penalising would cause false negatives.

---

## Audience in Cache Keys

The cache key for every SerpApi call must include audience. The existing `SerpApiCache.make_key(engine, params)` hashes the params dict. Since audience is injected into the `q` param of every query (via the search_query from the parser prompt, which includes the gender word), the cache key automatically differs between male and female runs **for Shopping queries**.

For Maps queries, audience is injected explicitly into the `q` param (e.g. `"Nike store men"` vs `"Nike store women"`). The Maps cache key differs because `q` differs.

---

## Radius Enforcement Design

```
User's actual lat/lng (from browser, not rounded)
    ↓
POST /api/offline {lat, lng, ...}
    ↓
find_nearby_stores():
    - ll param for Maps uses rounded lat/lng (cache-friendly)
    - After Maps results arrive:
        distance = haversine(user_lat, user_lng, store_lat, store_lng)  ← actual coords
        if distance > OFFLINE_RADIUS_KM: exclude
        if store has no coordinates: exclude
    - Circle drawn on map with OFFLINE_RADIUS_KM regardless of results
    - If stores == []: return OfflineResult(stores=[], ..., empty_radius=True)
```

### The empty-radius state
A new `empty_radius: bool` field on `OfflineResult`. When `True`:
- Frontend shows: "No stores available within 50 km"
- Map still renders, centred on user location, 50 km circle drawn, no markers
- Online-only sellers list still shown

### Named Constant
`OFFLINE_RADIUS_KM = 50` in `store_finder.py`. The frontend receives it from the `offline_complete` event so it draws the correct circle.

---

## Decisions Made Here

| # | Decision | Choice | Reason |
|---|----------|--------|--------|
| D18 | Audience cache key | Injected into `q` param naturally (via prompt + finder) | No separate cache-key field needed; the query string already differs |
| D19 | Gender-neutral categories | Fixed set in verifier; no penalty for audience mismatch | Avoids false negatives on unisex products |
| D20 | Audience data model | `Literal["male", "female"]` string, not bool | Easy to extend to "kids", "unisex" later; Pydantic validates it |
| D21 | Radius constant | Named constant in `store_finder.py`, not config | Brief says behaviour is fixed at 50 km; config would imply it's tunable |
| D22 | Radius for Maps `ll` param | Zoom level `14z` kept; radius enforced in code, not by zoom | SerpApi doesn't accept a radius param for Maps; zoom is a display hint only |
| D23 | Frontend selector | Two-button toggle (not radio group) | Matches existing design system; clearer touch target; ARIA-labeled |
| D24 | Re-run prompt after audience change | Non-modal confirm strip below results | Blocks accidental re-runs; doesn't modal-block the user |
| D25 | Selector persistence | Session only (React state, no localStorage) | Brief requires no carry-over between visits; localStorage would carry over |
| D26 | Stores with no coordinates | Excluded from map and list | Cannot verify within 50 km; honest to exclude rather than show unverified |
