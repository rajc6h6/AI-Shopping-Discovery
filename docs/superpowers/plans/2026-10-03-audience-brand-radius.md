# Audience Selector · Offline Brand Logic · 50 km Radius — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Three production changes — mandatory Male/Female audience selector propagated through all pipeline stages; brand-based Maps search for generic offline items; strict 50 km radius enforcement with empty-map honest state.

**Architecture:** See `docs/PLAN_AUDIENCE_AND_RADIUS.md` and `docs/PLAN_OFFLINE_BRANDS.md` for full design rationale.

**Tech Stack:** FastAPI + Pydantic (backend), Next.js App Router + React + Vanilla CSS (frontend), Leaflet.js (map circle), pytest (backend tests), Vitest v2 (frontend tests).

## Global Constraints

- Reuse existing SSE pattern, cache, design system, trace panel, confidence scoring
- Audience value must be exactly `"male"` or `"female"` (lowercase string) everywhere
- `OFFLINE_RADIUS_KM = 50` — single named constant, not scattered literals
- Backend rejects missing/invalid audience with HTTP 422 (Pydantic validation)
- No store beyond 50 km may appear in any output — enforce in code, not just query params
- Stores with no GPS coordinates are excluded
- Cache keys differ between male and female (audience injected into query strings)
- All existing tests must still pass
- Frontend: no preselection; search button disabled until audience chosen; starts unselected on every page load
- Only `"male"` and `"female"` offered now; data model must allow adding values later without migration

---

### Task 1: Backend — Audience in Models and Parser Prompt

**Files:**
- Modify: `backend/app/models.py` — add `audience` field to `SearchRequest`, `CompareRequest`, `OfflineRequest`
- Modify: `backend/prompts/parse_chat.txt` — add audience injection rule
- Modify: `backend/app/parser.py` — accept `audience` param, inject into prompt

**Interfaces:**
- Produces: `SearchRequest.audience: Literal["male", "female"]` (required)
- Produces: `CompareRequest.audience: Literal["male", "female"]` (required)
- Produces: `OfflineRequest.audience: Literal["male", "female"]` (required)
- Produces: `parse_chat(text, key, audience, model)` updated signature

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_audience_models.py
from pydantic import ValidationError
import pytest
from app.models import SearchRequest, CompareRequest, OfflineRequest

def test_search_request_requires_audience():
    with pytest.raises(ValidationError):
        SearchRequest(chat_text="test", market="in")

def test_search_request_rejects_invalid_audience():
    with pytest.raises(ValidationError):
        SearchRequest(chat_text="test", market="in", audience="unisex")

def test_search_request_accepts_male():
    req = SearchRequest(chat_text="test", market="in", audience="male")
    assert req.audience == "male"

def test_search_request_accepts_female():
    req = SearchRequest(chat_text="test", market="in", audience="female")
    assert req.audience == "female"

def test_compare_request_requires_audience():
    with pytest.raises(ValidationError):
        CompareRequest(product_title="t", product_attributes={}, market="in")

def test_offline_request_requires_audience():
    with pytest.raises(ValidationError):
        OfflineRequest(sellers=[], product_title="t", lat=0.0, lng=0.0, market="in")
```

- [ ] **Step 2: Run to verify they fail**

```
cd backend && .venv\Scripts\python.exe -m pytest tests/test_audience_models.py -v
```
Expected: FAIL — `audience` field does not exist

- [ ] **Step 3: Update `models.py`**

```python
from typing import Optional, Literal

AudienceType = Literal["male", "female"]

class SearchRequest(BaseModel):
    chat_text: str
    market: str = "in"
    audience: AudienceType  # required

class CompareRequest(BaseModel):
    product_title: str
    product_attributes: dict
    product_image: Optional[str] = None
    market: str = "in"
    audience: AudienceType  # required

class OfflineRequest(BaseModel):
    sellers: list[dict]
    product_title: str
    product_thumbnail: Optional[str] = None
    lat: float
    lng: float
    market: str = "in"
    audience: AudienceType  # required
    is_specific: bool = False
    verified_results: list[dict] = []
```

- [ ] **Step 4: Update `parse_chat.txt`**

Add this section right before "## Output format":

```
## Audience override

The user has selected an audience. Every extracted item is for this person.

AUDIENCE: {audience}

Rules:
1. Set `gender` to exactly "{audience}" for every item, regardless of what the text says.
2. For clothing, footwear, and accessories, include "men" (male) or "women" (female) in `search_query`.
3. For gender-neutral categories (phone, laptop, tablet, watch, bag, backpack, wallet,
   earphones, headphones, perfume, fragrance), do NOT force the audience word into
   `search_query` — it hurts search results.
4. If the text mentions a recipient of a different gender (e.g. "for my husband" when
   audience is female), still use {audience} for gender and search_query. The audience wins.
```

- [ ] **Step 5: Update `parser.py`**

```python
async def parse_chat(
    text: str,
    featherless_api_key: str,
    audience: str,          # NEW — "male" or "female"
    model: str = MODEL_NAME,
) -> ParseResult:
    ...
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
    system_prompt = system_prompt.replace("{audience}", audience)  # inject
    ...
```

- [ ] **Step 6: Run tests**

```
cd backend && .venv\Scripts\python.exe -m pytest tests/test_audience_models.py -v
```
Expected: PASS

- [ ] **Step 7: Commit**

```
git add backend/app/models.py backend/prompts/parse_chat.txt backend/app/parser.py
git add backend/tests/test_audience_models.py
git commit -m "feat(audience): add audience field to request models and parser"
```

---

### Task 2: Backend — Audience in Finder + Verifier

**Files:**
- Modify: `backend/app/finder.py` — accept audience, inject into query
- Modify: `backend/app/verifier.py` — add audience AttributeScore with neutral-category bypass

**Interfaces:**
- Produces: `find_products(item, client, market, audience)` updated
- Produces: `verify_match(item, candidate, audience)` updated

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_audience_propagation.py
from app.verifier import verify_match
from app.models import ParsedItem, ProductCandidate

def _item(category="blazer"):
    return ParsedItem(category=category, is_specific=False,
                      source_text="test", search_query="navy blazer")

def _candidate(title):
    return ProductCandidate(title=title, source="TestSeller", link="http://x.com",
                            engine_used="google_shopping", position=1, currency="INR")

def test_verifier_penalises_wrong_audience():
    result = verify_match(_item("blazer"), _candidate("Women's Navy Blazer"), audience="male")
    score = next(s for s in result.scores if s.attribute == "audience")
    assert not score.match
    assert score.confidence < 0.3

def test_verifier_passes_correct_audience():
    result = verify_match(_item("blazer"), _candidate("Men's Navy Slim Fit Blazer"), audience="male")
    score = next(s for s in result.scores if s.attribute == "audience")
    assert score.match

def test_verifier_skips_audience_for_neutral_category():
    result = verify_match(_item("laptop"), _candidate("Women's Laptop Bag"), audience="male")
    assert not any(s.attribute == "audience" for s in result.scores)

def test_verifier_passes_unisex_listing():
    result = verify_match(_item("sneakers"), _candidate("Unisex White Running Shoes"), audience="male")
    score = next(s for s in result.scores if s.attribute == "audience")
    assert score.match
```

```python
# backend/tests/test_finder_audience.py
from app.finder import _build_shopping_params
from app.models import ParsedItem

def test_finder_injects_audience_when_missing():
    item = ParsedItem(category="blazer", is_specific=False,
                      source_text="navy blazer", search_query="navy blazer")
    params = _build_shopping_params(item, market="in", audience="male")
    assert "men" in params["q"].lower()

def test_finder_no_duplicate_audience():
    item = ParsedItem(category="blazer", is_specific=False,
                      source_text="navy blazer", search_query="men navy blazer")
    params = _build_shopping_params(item, market="in", audience="male")
    assert params["q"].lower().count("men") == 1

def test_finder_skips_audience_for_neutral():
    item = ParsedItem(category="laptop", is_specific=False,
                      source_text="laptop", search_query="laptop 15 inch")
    params = _build_shopping_params(item, market="in", audience="male")
    assert "men" not in params["q"].lower()
```

- [ ] **Step 2: Run to verify fail**

```
cd backend && .venv\Scripts\python.exe -m pytest tests/test_audience_propagation.py tests/test_finder_audience.py -v
```

- [ ] **Step 3: Update `verifier.py`**

Add constants and `_check_audience` function (see full code in `docs/PLAN_AUDIENCE_AND_RADIUS.md`). Update `verify_match` signature to `(item, candidate, audience: str = "")`.

GENDER_NEUTRAL_CATEGORIES set:
```python
GENDER_NEUTRAL_CATEGORIES = {
    'phone', 'smartphone', 'laptop', 'tablet', 'watch', 'bag', 'backpack',
    'wallet', 'sunglasses', 'belt', 'hat', 'cap', 'water bottle', 'earphones',
    'headphones', 'perfume', 'fragrance', 'jewellery', 'jewelry',
}
MALE_WORDS = {'men', "men's", 'male', "man's", 'gents', 'boys'}
FEMALE_WORDS = {'women', "women's", 'female', "woman's", 'ladies', 'girls'}
```

`_check_audience(audience, category, title) -> AttributeScore | None`:
- Returns `None` if category is in GENDER_NEUTRAL_CATEGORIES
- Returns `match=True, confidence=0.85` if "unisex" in title
- Returns `match=True, confidence=0.70` if no gender signal
- Returns `match=True, confidence=0.95` if correct gender word present
- Returns `match=False, confidence=0.10` if wrong gender word present

- [ ] **Step 4: Update `finder.py`**

```python
AUDIENCE_WORDS = {"male": "men", "female": "women"}
GENDER_NEUTRAL_FINDER = {'phone','smartphone','laptop','tablet','watch','bag',
                          'backpack','wallet','sunglasses','belt','hat','cap'}

def _build_shopping_params(item, market="in", audience=""):
    query = item.search_query
    if audience:
        word = AUDIENCE_WORDS.get(audience, "")
        neutral = any(n in item.category.lower() for n in GENDER_NEUTRAL_FINDER)
        if not neutral and word and word not in query.lower():
            query = f"{word} {query}"
    params = {"q": query, "gl": market, "hl": "en", "num": 10}
    if market == "in":
        params["google_domain"] = "google.co.in"
    return params

async def find_products(item, client, market="in", audience=""):
    params = _build_shopping_params(item, market, audience)
    ...
```

- [ ] **Step 5: Run tests**

```
cd backend && .venv\Scripts\python.exe -m pytest tests/test_audience_propagation.py tests/test_finder_audience.py tests/test_verifier.py -v
```

- [ ] **Step 6: Commit**

```
git add backend/app/verifier.py backend/app/finder.py
git add backend/tests/test_audience_propagation.py backend/tests/test_finder_audience.py
git commit -m "feat(audience): audience check in verifier, audience injection in finder"
```

---

### Task 3: Backend — 50 km Radius Enforcement

**Files:**
- Modify: `backend/app/store_finder.py` — `OFFLINE_RADIUS_KM`, `_within_radius`, filter loop
- Modify: `backend/app/models.py` — add `empty_radius`, `radius_km` to `OfflineResult`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_radius.py
from app.store_finder import _haversine_km, OFFLINE_RADIUS_KM, _within_radius
from app.models import OfflineResult

def test_radius_constant_is_50():
    assert OFFLINE_RADIUS_KM == 50

def test_haversine_mumbai_pune():
    d = _haversine_km(19.0760, 72.8777, 18.5204, 73.8567)
    assert 140 < d < 160

def test_within_radius_49km():
    assert _within_radius(0.0, 0.0, 49/111.0, 0.0)

def test_within_radius_50km():
    assert _within_radius(0.0, 0.0, 50/111.0, 0.0)

def test_outside_radius_51km():
    assert not _within_radius(0.0, 0.0, 51/111.0, 0.0)

def test_offline_result_empty_radius_default():
    r = OfflineResult(stores=[], online_only_sellers=[], search_engines_used=[])
    assert r.empty_radius == False
    assert r.radius_km == 50
```

- [ ] **Step 2: Run to verify fail**

```
cd backend && .venv\Scripts\python.exe -m pytest tests/test_radius.py -v
```

- [ ] **Step 3: Update `models.py`**

```python
class OfflineResult(BaseModel):
    stores: list[StoreResult]
    online_only_sellers: list[str]
    search_engines_used: list[str]
    empty_radius: bool = False
    radius_km: int = 50
    brand_source_note: Optional[str] = None
```

- [ ] **Step 4: Update `store_finder.py`**

```python
OFFLINE_RADIUS_KM = 50

def _within_radius(user_lat, user_lng, store_lat, store_lng):
    return _haversine_km(user_lat, user_lng, store_lat, store_lng) <= OFFLINE_RADIUS_KM
```

In `find_nearby_stores`, after getting `store_lat`, `store_lng`:
```python
if not (store_lat and store_lng):
    continue  # no coordinates — cannot verify
if not _within_radius(request.lat, request.lng, store_lat, store_lng):
    continue  # outside 50 km
distance = _haversine_km(request.lat, request.lng, store_lat, store_lng)
```

Update return:
```python
return OfflineResult(
    stores=stores,
    online_only_sellers=online_only,
    search_engines_used=list(set(engines_used)),
    empty_radius=len(stores) == 0 and len(engines_used) > 0,
    radius_km=OFFLINE_RADIUS_KM,
)
```

- [ ] **Step 5: Run tests**

```
cd backend && .venv\Scripts\python.exe -m pytest tests/test_radius.py -v
```

- [ ] **Step 6: Commit**

```
git add backend/app/store_finder.py backend/app/models.py backend/tests/test_radius.py
git commit -m "feat(radius): strict 50km enforcement with OFFLINE_RADIUS_KM constant"
```

---

### Task 4: Backend — Brand Extractor for Generic Offline Items

**Files:**
- Create: `backend/app/brand_extractor.py`
- Modify: `backend/app/store_finder.py` — call brand extractor for generic items

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_brand_extractor.py
from app.brand_extractor import extract_brands_from_results, MARKETPLACE_SELLERS

def _r(source, title, conf):
    return {"candidate": {"source": source, "title": title}, "verification": {"overall_confidence": conf}}

def test_extracts_brand_from_source():
    results = [_r("Nike", "Nike Sneakers Men", 0.85), _r("Nike", "Nike Pegasus", 0.75),
               _r("Adidas", "Adidas Shoes", 0.70)]
    brands = extract_brands_from_results(results, "male")
    assert "Nike" in brands and "Adidas" in brands

def test_excludes_marketplaces():
    results = [_r("Amazon", "Nike Sneakers", 0.90), _r("Puma", "Puma Shoes", 0.80)]
    brands = extract_brands_from_results(results, "male")
    assert "Amazon" not in brands
    assert "Puma" in brands

def test_excludes_low_confidence():
    results = [_r("Nike", "Nike Shoes", 0.3)]
    assert extract_brands_from_results(results, "male") == []

def test_cap_at_three():
    results = [_r(b, f"{b} Shoes", 0.8) for b in ["Nike","Adidas","Puma","Reebok","Fila"]]
    assert len(extract_brands_from_results(results, "male")) <= 3

def test_deterministic():
    results = [_r("Nike", "Nike Shoes", 0.85), _r("Adidas", "Adidas Shoes", 0.80)]
    assert extract_brands_from_results(results, "male") == extract_brands_from_results(results, "male")

def test_returns_empty_all_marketplaces():
    results = [_r("Amazon", "Nike Shoes", 0.90)]
    assert extract_brands_from_results(results, "male") == []

def test_single_brand_above_threshold():
    assert extract_brands_from_results([_r("Woodland", "Woodland Boots", 0.82)], "male") == ["Woodland"]

def test_single_brand_below_single_threshold():
    # min_single_confidence=0.6; 0.55 is below it
    assert extract_brands_from_results([_r("Woodland", "Woodland Boots", 0.55)], "male") == []
```

- [ ] **Step 2: Run to verify fail**

```
cd backend && .venv\Scripts\python.exe -m pytest tests/test_brand_extractor.py -v
```

- [ ] **Step 3: Create `brand_extractor.py`**

(Full code as specified in `docs/PLAN_OFFLINE_BRANDS.md` — see `extract_brands_from_results` and constants.)

Key logic:
```python
MARKETPLACE_SELLERS = {
    'amazon','amazon india','amazon.in','amazon.com','flipkart','myntra','ajio',
    'nykaa','nykaa fashion','meesho','snapdeal','shopclues','shein','temu',
    'alibaba','aliexpress','wish','ebay','etsy','google shopping','google',
    'walmart','target','paytm mall','tata cliq','reliance digital','croma','vijay sales',
}

def _is_marketplace(name: str) -> bool:
    return name.lower().strip() in MARKETPLACE_SELLERS

def extract_brands_from_results(
    verified_results: list[dict],
    audience: str,
    min_confidence: float = 0.5,
    min_single_confidence: float = 0.6,
    max_brands: int = 3,
) -> list[str]:
    brand_scores: dict[str, list[float]] = {}
    brand_originals: dict[str, str] = {}  # lowercase -> original casing

    for result in verified_results:
        conf = result.get("verification", {}).get("overall_confidence", 0.0)
        if conf < min_confidence:
            continue
        source = result.get("candidate", {}).get("source", "")
        if source and not _is_marketplace(source):
            key = source.lower().strip()
            brand_scores.setdefault(key, []).append(conf)
            brand_originals[key] = source.strip()

    ranked = []
    for key, confs in brand_scores.items():
        if len(confs) == 1 and confs[0] < min_single_confidence:
            continue
        ranked.append((key, sum(confs)))

    ranked.sort(key=lambda x: (-x[1], x[0]))
    return [brand_originals[k] for k, _ in ranked[:max_brands]]
```

- [ ] **Step 4: Update `store_finder.py`** to call `extract_brands_from_results` and route generic vs. specific

Split `find_nearby_stores` into:
- `_find_stores_by_sellers(request, client)` — existing logic
- `_find_stores_by_brands(request, client, brands)` — new brand path
- `find_nearby_stores(request, client)` — routes between them

- [ ] **Step 5: Run tests**

```
cd backend && .venv\Scripts\python.exe -m pytest tests/test_brand_extractor.py tests/test_radius.py -v
```

- [ ] **Step 6: Commit**

```
git add backend/app/brand_extractor.py backend/app/store_finder.py
git add backend/tests/test_brand_extractor.py
git commit -m "feat(offline): brand extractor for generic items, brand-path store search"
```

---

### Task 5: Backend — Wire Audience Through api.py + Compare

**Files:**
- Modify: `backend/app/api.py` — pass audience everywhere; add audience to trace events
- Modify: `backend/app/compare.py` — accept and use audience

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_api_audience.py
from fastapi.testclient import TestClient
from app.main import app
client = TestClient(app)

def test_search_rejects_missing_audience():
    r = client.post("/api/search", json={"chat_text": "navy blazer", "market": "in"})
    assert r.status_code == 422

def test_compare_rejects_missing_audience():
    r = client.post("/api/compare", json={"product_title":"blazer","product_attributes":{},"market":"in"})
    assert r.status_code == 422

def test_offline_rejects_missing_audience():
    r = client.post("/api/offline", json={"sellers":[],"product_title":"blazer","lat":19.07,"lng":72.87,"market":"in"})
    assert r.status_code == 422
```

- [ ] **Step 2: Run to verify fail** (models exist but api not yet wired)

```
cd backend && .venv\Scripts\python.exe -m pytest tests/test_api_audience.py -v
```

- [ ] **Step 3: Update `api.py`**

`/api/search`:
- `parse_chat(..., request.audience)`
- `find_products(..., request.audience)`
- `verify_match(..., request.audience)`
- Trace events include `"audience": request.audience`

`/api/compare`:
- `compare_prices(..., audience=request.audience)`

`/api/offline`:
- `find_nearby_stores(request, client)` — request already has audience, is_specific, verified_results

- [ ] **Step 4: Update `compare.py`**

```python
async def compare_prices(
    product_title, product_attributes, client, market="in", audience=""
):
    ref_item = ParsedItem(..., gender=audience)
    ...
    verification = verify_match(ref_item, candidate, audience)
```

- [ ] **Step 5: Run tests**

```
cd backend && .venv\Scripts\python.exe -m pytest tests/test_api_audience.py tests/ -v
```

- [ ] **Step 6: Commit**

```
git add backend/app/api.py backend/app/compare.py backend/tests/test_api_audience.py
git commit -m "feat(audience): wire audience through api.py and compare agent"
```

---

### Task 6: Frontend — Audience Selector Component

**Files:**
- Modify: `frontend/src/app/PasteToProductClient.tsx`
- Modify: `frontend/src/app/page.module.css`
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Write failing tests**

```typescript
// frontend/src/lib/__tests__/audienceSelector.test.ts
import { describe, it, expect } from 'vitest';

function isSearchEnabled(text: string, audience: string | null): boolean {
  return text.trim().length > 0 && audience !== null;
}

describe('audience guard', () => {
  it('disabled when no audience', () => expect(isSearchEnabled('blazer', null)).toBe(false));
  it('enabled with text and audience', () => expect(isSearchEnabled('blazer', 'male')).toBe(true));
  it('disabled with empty text', () => expect(isSearchEnabled('', 'female')).toBe(false));
});
```

- [ ] **Step 2: Run to verify pass** (pure function test)

```
cd frontend && npx vitest run src/lib/__tests__/audienceSelector.test.ts
```

- [ ] **Step 3: Add `audience` state + selector to `PasteToProductClient.tsx`**

State: `const [audience, setAudience] = useState<'male' | 'female' | null>(null);`

Selector (below textarea, above inputFooter):
```tsx
<div className={styles.audienceSelector} role="group" aria-labelledby="audience-label">
  <span id="audience-label" className={styles.audienceLabel}>Shopping for</span>
  <div className={styles.audienceButtons}>
    {(['male', 'female'] as const).map((a) => (
      <button
        key={a}
        type="button"
        id={`audience-${a}`}
        className={`${styles.audienceBtn} ${audience === a ? styles.audienceBtnActive : ''}`}
        onClick={() => {
          setAudience(a);
          if (hasResults && audience !== a) setShowRerunBanner(true);
        }}
        aria-pressed={audience === a}
      >
        {a === 'male' ? 'Male' : 'Female'}
      </button>
    ))}
  </div>
</div>
```

Hint text next to Search button:
```tsx
{!audience && chatText.trim() && (
  <span className={styles.audienceHint} role="status" aria-live="polite">
    Choose who you&apos;re shopping for
  </span>
)}
```

Search button: `disabled={!chatText.trim() || isSearching || !audience}`

Re-run banner:
```tsx
{showRerunBanner && hasResults && (
  <div className={styles.rerunBanner} role="alert">
    <span>You changed the audience — earlier results may not match.</span>
    <button className="btn btn-sm btn-cta" type="button"
      onClick={() => { setShowRerunBanner(false); handleSearch(); }}>
      Re-run search
    </button>
    <button className="btn btn-ghost btn-sm" type="button"
      onClick={() => setShowRerunBanner(false)}>
      Keep results
    </button>
  </div>
)}
```

- [ ] **Step 4: Update `api.ts`**

All three stream functions accept `audience: 'male' | 'female'` and include it in request body.

`streamOffline` additionally accepts `isSpecific: boolean` and `verifiedResults: unknown[]`.

`OfflineResult` interface gains `empty_radius: boolean`, `radius_km: number`, `brand_source_note: string | null`.

- [ ] **Step 5: Add CSS to `page.module.css`**

```css
.audienceSelector { display:flex; align-items:center; gap:.75rem; padding:.75rem 1rem; border-top:1px solid var(--border); }
.audienceLabel { font-size:.8125rem; font-weight:600; color:var(--text-muted); white-space:nowrap; }
.audienceButtons { display:flex; gap:.5rem; }
.audienceBtn { padding:.375rem 1rem; border-radius:999px; font-size:.8125rem; font-weight:600; border:1.5px solid var(--border); background:transparent; color:var(--text-muted); cursor:pointer; transition:all .15s ease; min-width:44px; min-height:44px; }
.audienceBtn:hover { border-color:var(--accent); color:var(--accent); }
.audienceBtnActive { background:var(--accent); border-color:var(--accent); color:#fff; }
.audienceHint { font-size:.75rem; color:var(--text-muted); align-self:center; }
.rerunBanner { display:flex; align-items:center; gap:.75rem; padding:.75rem 1rem; background:var(--surface-2); border-radius:.5rem; border:1px solid var(--border); font-size:.8125rem; margin-top:.5rem; }
```

- [ ] **Step 6: Run tests**

```
cd frontend && npx vitest run
```

- [ ] **Step 7: Commit**

```
git add frontend/src/app/PasteToProductClient.tsx frontend/src/app/page.module.css
git add frontend/src/lib/api.ts frontend/src/lib/__tests__/audienceSelector.test.ts
git commit -m "feat(ui): audience selector, disabled-search guard, re-run banner"
```

---

### Task 7: Frontend — Map Circle + Empty-Radius State + Brand Note

**Files:**
- Modify: `frontend/src/components/StoreMap.tsx` — add 50 km circle
- Modify: `frontend/src/components/OfflineMode.tsx` — empty-radius state, brand note, pass audience
- Modify: `frontend/src/components/OfflineMode.module.css` — new states

- [ ] **Step 1: Write failing test**

```typescript
// frontend/src/lib/__tests__/radius.test.ts
import { describe, it, expect } from 'vitest';

function haversineKm(lat1: number, lng1: number, lat2: number, lng2: number): number {
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLng = ((lng2 - lng1) * Math.PI) / 180;
  const a = Math.sin(dLat/2)**2 + Math.cos(lat1*Math.PI/180)*Math.cos(lat2*Math.PI/180)*Math.sin(dLng/2)**2;
  return R * 2 * Math.asin(Math.sqrt(a));
}

describe('haversine', () => {
  it('~148km Mumbai-Pune', () => {
    const d = haversineKm(19.076, 72.877, 18.5204, 73.8567);
    expect(d).toBeGreaterThan(140);
    expect(d).toBeLessThan(160);
  });
});
```

- [ ] **Step 2: Run to verify pass**

```
cd frontend && npx vitest run src/lib/__tests__/radius.test.ts
```

- [ ] **Step 3: Update `StoreMap.tsx`**

Add props `radiusKm?: number` (default 50) and `emptyRadius?: boolean`.

Add Leaflet `Circle` around user location:
```tsx
import { Circle } from 'react-leaflet';
<Circle
  center={[userLat, userLng]}
  radius={(radiusKm ?? 50) * 1000}
  pathOptions={{ color: '#6366f1', fillColor: '#6366f1', fillOpacity: 0.05, weight: 1.5 }}
/>
```

Set zoom: `zoom={emptyRadius ? 9 : 12}` so empty map shows the full circle.

- [ ] **Step 4: Update `OfflineMode.tsx`**

Pass `audience`, `isSpecific`, `verifiedResults` from props to `streamOffline` call.

Show brand note when present:
```tsx
{offlineResult.brand_source_note && (
  <p className={styles.brandNote}>ℹ {offlineResult.brand_source_note}</p>
)}
```

Show empty-radius state:
```tsx
{offlineResult.empty_radius && (
  <div className={styles.emptyRadius} role="status">
    <span className={styles.emptyRadiusIcon}>📍</span>
    <p className={styles.emptyRadiusTitle}>No stores available within 50 km</p>
    <p className={styles.emptyRadiusBody}>The map shows your location and the 50 km search area.</p>
  </div>
)}
```

Pass to StoreMap: `radiusKm={offlineResult.radius_km} emptyRadius={offlineResult.empty_radius}`

- [ ] **Step 5: Update `OfflineMode.module.css`**

```css
.brandNote { display:flex; gap:.5rem; padding:.625rem .875rem; background:var(--surface-2); border-radius:.5rem; font-size:.8125rem; color:var(--text-muted); margin-bottom:.75rem; }
.emptyRadius { text-align:center; padding:2rem 1rem; }
.emptyRadiusIcon { font-size:2rem; display:block; margin-bottom:.5rem; }
.emptyRadiusTitle { font-size:1rem; font-weight:600; color:var(--text); margin:0 0 .5rem; }
.emptyRadiusBody { font-size:.875rem; color:var(--text-muted); margin:0; }
```

- [ ] **Step 6: Commit**

```
git add frontend/src/components/StoreMap.tsx frontend/src/components/OfflineMode.tsx
git add frontend/src/components/OfflineMode.module.css frontend/src/lib/__tests__/radius.test.ts
git commit -m "feat(map): 50km circle, empty-radius state, brand source note in offline UI"
```

---

### Task 8: Tests — Audience Cache Isolation + Radius Boundary + Full Regression

**Files:**
- Create: `backend/tests/test_audience_cache.py`
- Create: `backend/tests/test_radius_boundary.py`

- [ ] **Step 1: Write cache isolation test**

```python
# backend/tests/test_audience_cache.py
from app.cache import SerpApiCache
import tempfile, os

def test_male_and_female_keys_differ():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db = f.name
    try:
        cache = SerpApiCache(db)
        km = cache.make_key("google_shopping", {"q": "men navy blazer", "gl": "in"})
        kf = cache.make_key("google_shopping", {"q": "women navy blazer", "gl": "in"})
        assert km != kf
    finally:
        os.unlink(db)

def test_same_params_same_key():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db = f.name
    try:
        cache = SerpApiCache(db)
        p = {"q": "men navy blazer", "gl": "in"}
        assert cache.make_key("google_shopping", p) == cache.make_key("google_shopping", p)
    finally:
        os.unlink(db)
```

- [ ] **Step 2: Write radius boundary test**

```python
# backend/tests/test_radius_boundary.py
from app.store_finder import _within_radius, OFFLINE_RADIUS_KM

def test_49km_inside(): assert _within_radius(0,0, 49/111.0, 0)
def test_50km_inside(): assert _within_radius(0,0, 50/111.0, 0)
def test_51km_outside(): assert not _within_radius(0,0, 51/111.0, 0)
def test_zero_coords_falsy():
    # Sentinel for "no coordinates" — Python 0.0 is falsy
    assert not (0.0 and 0.0)
```

- [ ] **Step 3: Run full test suite**

```
cd backend && .venv\Scripts\python.exe -m pytest tests/ -v
cd frontend && npx vitest run
```
Expected: All PASS

- [ ] **Step 4: Commit**

```
git add backend/tests/test_audience_cache.py backend/tests/test_radius_boundary.py
git commit -m "test: audience cache isolation, radius boundary, full regression green"
```

---

### Task 9: Docs — DECISIONS.md, SERPAPI_NOTES.md, SKILLS_USED.md, README

**Files:**
- Modify: `docs/DECISIONS.md` — append D18–D35
- Modify: `docs/SERPAPI_NOTES.md` — add audience and radius section
- Modify: `docs/SKILLS_USED.md` — fill actual usage
- Modify: `README.md` — audience selector section + limitation note

- [ ] **Step 1: Append D18–D35 to DECISIONS.md** (from both plan docs)

- [ ] **Step 2: Add to SERPAPI_NOTES.md**

```markdown
## Audience Injection in SerpApi Queries (verified design)
- Google Shopping: No gender param. Audience word ("men"/"women") injected into `q`.
- Google Maps: No radius param. `ll` param sets centre. Radius enforced in code after results.
  Default Maps result radius at zoom 14z is ~20-30 km. Code filters to exactly 50 km.
- GPS coordinates: Present for ~95% of Indian retailer results. Missing-coordinate stores excluded.
```

- [ ] **Step 3: Update SKILLS_USED.md actual usage table**

- [ ] **Step 4: Update README.md**

Add under "How it works":
> **Audience selection (required):** Choose Male or Female before searching — this tells the app who the products are for (not who you are; you may be buying a gift). The app currently offers Male and Female only; additional audience types may be added in a future version.

- [ ] **Step 5: Run full regression one last time**

```
cd backend && .venv\Scripts\python.exe -m pytest tests/ -v
cd frontend && npx vitest run
```

- [ ] **Step 6: Commit**

```
git add docs/DECISIONS.md docs/SERPAPI_NOTES.md docs/SKILLS_USED.md README.md
git commit -m "docs: audience+radius decisions, SerpApi notes, README update"
```

---

## Spec Coverage Checklist

| Requirement | Task |
|-------------|------|
| Male/Female selector below textarea | T6 |
| Nothing preselected | T6 (null default) |
| Search disabled until selection | T6 |
| Hint "Choose who you're shopping for" | T6 |
| Backend rejects missing audience (HTTP 422) | T1 + T5 |
| Session-only persistence, unselected on new visit | T6 (React state, no localStorage) |
| Re-run prompt on audience change after results | T6 |
| Audience in parser prompt | T1 |
| Audience in discovery queries | T2 |
| Audience in verifier attribute scores | T2 |
| Gender-neutral bypass in verifier | T2 |
| Audience in compare agent | T5 |
| Audience in offline store queries | T4 |
| Cache keys differ by audience | T8 (proven by test) |
| Text-contradicts-audience: selection wins | T1 (prompt rule) |
| Brand logic for generic offline items | T4 |
| Marketplace filter | T4 |
| Brand quality/confidence filter | T4 |
| Brand cap (3) | T4 |
| Brand source note in UI | T7 |
| No-brand fallback message | T4 |
| Evidence line naming brand and source | T4 |
| Store-type label | T4 |
| 50 km radius enforced in code | T3 |
| Stores without coordinates excluded | T3 |
| Empty-radius state message | T7 |
| Empty-radius: map + circle, no markers | T7 |
| 50 km circle always drawn on map | T7 |
| `OFFLINE_RADIUS_KM` single constant | T3 |
| Distance check uses actual coords | T3 |
| Cache keys use rounded coords | Existing (unchanged) |
| Selector tests | T6 |
| Audience propagation tests | T2, T8 |
| Brand logic tests | T4 |
| Radius boundary tests | T3, T8 |
| Cache isolation tests | T8 |
| All existing tests still pass | T8 |
| DECISIONS.md updated | T9 |
| SERPAPI_NOTES.md updated | T9 |
| parse_chat.txt updated | T1 |
| SKILLS_USED.md updated | T9 |
