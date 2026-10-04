# Paste-to-Product Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working "Paste-to-Product" app — paste AI style advice, get real buyable products with confidence scores, then compare prices across platforms.

**Architecture:** FastAPI backend (Python 3.12) with SSE streaming → Next.js 14 App Router frontend (React 18). SerpApi via direct `httpx` calls with SQLite cache. LLM via AWS Bedrock (Claude 3 Haiku for parsing). Monorepo: `backend/` + `frontend/`.

**Tech Stack:**
- Backend: Python 3.12, FastAPI, httpx, sqlite3, boto3, sse-starlette, pydantic
- Frontend: Next.js 14, React 18, TypeScript, vanilla CSS
- Deployment: Vercel (frontend) + Render (backend)

## Global Constraints

- All SerpApi responses cached by normalised request key in SQLite. Never make a duplicate call.
- Session hard cap: 50 SerpApi calls. Per-item cap: 2 discovery calls. Per-compare: 4 calls.
- No secrets in code or repo. All keys from environment variables: `SERPAPI_API_KEY`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`.
- No fabricated products, prices, images, links, or reviews. Unknown = unknown.
- Every product match must have a per-attribute confidence breakdown.
- All prompts in versioned files under `backend/prompts/`.
- Default market: India (`gl=in`, `amazon_domain=amazon.in`). Switchable to US.
- Demo mode: pre-cached responses for 3 scripted chats. Labelled `[cached]` in trace.
- Honest labelling: "Exact"/"Variant" only with evidence. Generic items = "Best match to your description".

---

### Task 1: Project Scaffolding and Core Configuration

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/main.py`
- Create: `backend/.env.example`
- Create: `frontend/` (via `npx create-next-app`)
- Create: `.gitignore`
- Create: `README.md` (initial)

**Interfaces:**
- Produces: `Settings` pydantic model with all config (API keys, cache path, credit caps, market defaults)
- Produces: FastAPI app instance with CORS, health endpoint
- Produces: Next.js app with basic structure

- [ ] **Step 1: Create backend directory and requirements.txt**

```
# backend/requirements.txt
fastapi==0.115.0
uvicorn[standard]==0.30.0
httpx==0.27.0
openai==1.50.0
pydantic==2.9.0
pydantic-settings==2.5.0
sse-starlette==2.1.0
python-dotenv==1.0.1
```

- [ ] **Step 2: Create config.py with Settings model**

```python
# backend/app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    serpapi_api_key: str
    openai_api_key: str
    cache_db_path: str = "cache/serpapi_cache.db"
    default_market: str = "in"  # "in" or "us"
    max_calls_per_session: int = 50
    max_calls_per_item: int = 2
    max_calls_per_compare: int = 4
    openai_model_parse: str = "gpt-4o-mini"
    openai_model_vision: str = "gpt-4o"
    demo_mode: bool = False

    class Config:
        env_file = ".env"
```

- [ ] **Step 3: Create main.py with FastAPI app, CORS, and health endpoint**

```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import Settings

settings = Settings()
app = FastAPI(title="Paste-to-Product", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok", "demo_mode": settings.demo_mode}
```

- [ ] **Step 4: Create .env.example**

```
SERPAPI_API_KEY=your-serpapi-key-here
OPENAI_API_KEY=your-openai-key-here
DEMO_MODE=false
DEFAULT_MARKET=in
```

- [ ] **Step 5: Scaffold Next.js frontend**

```bash
cd frontend
npx -y create-next-app@latest ./ --typescript --app --eslint --src-dir --no-tailwind --import-alias "@/*"
```

- [ ] **Step 6: Create .gitignore**

```
# .gitignore
__pycache__/
*.pyc
.env
node_modules/
.next/
cache/
.venv/
```

- [ ] **Step 7: Verify backend starts**

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
# curl http://localhost:8000/health → {"status": "ok"}
```

- [ ] **Step 8: Verify frontend starts**

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:3000
```

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat: project scaffolding — FastAPI backend + Next.js frontend"
```

---

### Task 2: SerpApi Client with Caching Layer

**Files:**
- Create: `backend/app/serpapi_client.py`
- Create: `backend/app/cache.py`
- Create: `backend/tests/test_cache.py`
- Create: `backend/tests/test_serpapi_client.py`

**Interfaces:**
- Produces: `SerpApiCache` class — `get(key: str) -> dict | None`, `set(key: str, data: dict) -> None`, `make_key(engine: str, params: dict) -> str`
- Produces: `SerpApiClient` class — `async search(engine: str, params: dict) -> dict` (auto-caches, respects session cap)
- Produces: `CallTracker` — tracks per-session call count, raises on cap

- [ ] **Step 1: Write failing tests for cache**

```python
# backend/tests/test_cache.py
import pytest, tempfile, os
from app.cache import SerpApiCache

def test_cache_miss_returns_none():
    with tempfile.TemporaryDirectory() as d:
        cache = SerpApiCache(os.path.join(d, "test.db"))
        assert cache.get("nonexistent") is None

def test_cache_set_and_get():
    with tempfile.TemporaryDirectory() as d:
        cache = SerpApiCache(os.path.join(d, "test.db"))
        cache.set("key1", {"title": "Test Product", "price": 29.99})
        result = cache.get("key1")
        assert result == {"title": "Test Product", "price": 29.99}

def test_make_key_normalises_params():
    cache = SerpApiCache(":memory:")
    key1 = cache.make_key("google_shopping", {"q": "shoes", "gl": "in"})
    key2 = cache.make_key("google_shopping", {"gl": "in", "q": "shoes"})
    assert key1 == key2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_cache.py -v
```
Expected: FAIL (module not found)

- [ ] **Step 3: Implement SerpApiCache**

```python
# backend/app/cache.py
import sqlite3, json, hashlib
from typing import Optional

class SerpApiCache:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, data TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        self.conn.commit()

    def make_key(self, engine: str, params: dict) -> str:
        normalised = json.dumps({"engine": engine, **dict(sorted(params.items()))}, sort_keys=True)
        return hashlib.sha256(normalised.encode()).hexdigest()

    def get(self, key: str) -> Optional[dict]:
        row = self.conn.execute("SELECT data FROM cache WHERE key = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def set(self, key: str, data: dict) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO cache (key, data) VALUES (?, ?)",
            (key, json.dumps(data))
        )
        self.conn.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_cache.py -v
```
Expected: 3/3 PASS

- [ ] **Step 5: Write failing tests for SerpApiClient**

```python
# backend/tests/test_serpapi_client.py
import pytest
from app.serpapi_client import SerpApiClient, CallCapExceeded

def test_call_cap_exceeded():
    client = SerpApiClient(api_key="fake", cache_db=":memory:", max_calls=2)
    # Simulate 2 calls then the 3rd should raise
    client._call_count = 2
    with pytest.raises(CallCapExceeded):
        client._check_cap()

def test_cache_key_used():
    client = SerpApiClient(api_key="fake", cache_db=":memory:", max_calls=50)
    key = client.cache.make_key("google_shopping", {"q": "test"})
    client.cache.set(key, {"shopping_results": [{"title": "Cached"}]})
    # Should return cached result without hitting API
    import asyncio
    result = asyncio.run(client.search("google_shopping", {"q": "test"}))
    assert result["shopping_results"][0]["title"] == "Cached"
```

- [ ] **Step 6: Run tests to verify they fail**

- [ ] **Step 7: Implement SerpApiClient**

```python
# backend/app/serpapi_client.py
import httpx
from typing import Any
from app.cache import SerpApiCache

class CallCapExceeded(Exception):
    pass

class SerpApiClient:
    BASE_URL = "https://serpapi.com/search.json"

    def __init__(self, api_key: str, cache_db: str, max_calls: int = 50):
        self.api_key = api_key
        self.cache = SerpApiCache(cache_db)
        self.max_calls = max_calls
        self._call_count = 0
        self._call_log: list[dict] = []

    def _check_cap(self):
        if self._call_count >= self.max_calls:
            raise CallCapExceeded(f"Session cap of {self.max_calls} SerpApi calls reached")

    async def search(self, engine: str, params: dict) -> dict:
        key = self.cache.make_key(engine, params)
        cached = self.cache.get(key)
        if cached is not None:
            self._call_log.append({"engine": engine, "params": params, "cached": True})
            return cached

        self._check_cap()
        full_params = {**params, "engine": engine, "api_key": self.api_key, "output": "json"}
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(self.BASE_URL, params=full_params)
            resp.raise_for_status()
            data = resp.json()

        self.cache.set(key, data)
        self._call_count += 1
        self._call_log.append({"engine": engine, "params": params, "cached": False})
        return data

    def get_call_log(self) -> list[dict]:
        return self._call_log

    def get_call_count(self) -> int:
        return self._call_count
```

- [ ] **Step 8: Run tests to verify they pass**

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat: SerpApi client with SQLite caching and call cap"
```

---

### Task 3: Chat Parser (LLM-Powered Item Extraction)

**Files:**
- Create: `backend/app/parser.py`
- Create: `backend/app/models.py`
- Create: `backend/prompts/parse_chat.txt`
- Create: `backend/tests/test_parser.py`

**Interfaces:**
- Consumes: OpenAI API key from Settings
- Produces: `ParsedItem` pydantic model — `category`, `colour`, `fit_style`, `material`, `gender`, `budget_hint`, `season`, `brand`, `model_name`, `is_specific: bool`, `source_text: str`, `search_query: str`
- Produces: `parse_chat(text: str) -> list[ParsedItem]` async function

- [ ] **Step 1: Create data models**

```python
# backend/app/models.py
from pydantic import BaseModel
from typing import Optional

class ParsedItem(BaseModel):
    category: str  # e.g. "sneakers", "overshirt", "chinos"
    colour: Optional[str] = None
    fit_style: Optional[str] = None
    material: Optional[str] = None
    gender: Optional[str] = None
    budget_hint: Optional[str] = None
    season: Optional[str] = None
    brand: Optional[str] = None
    model_name: Optional[str] = None
    is_specific: bool = False  # True if brand+model named
    source_text: str  # The original text this was extracted from
    search_query: str  # Constructed search query for SerpApi

class ParseResult(BaseModel):
    items: list[ParsedItem]
    raw_input_length: int
    parse_model: str
```

- [ ] **Step 2: Create parse prompt**

```
# backend/prompts/parse_chat.txt
You are a shopping item extractor. Given a pasted AI chat conversation about style or outfit advice, extract every shoppable item mentioned.

For each item, return a JSON object with these fields:
- category: the product type (e.g. "sneakers", "overshirt", "chinos", "watch")
- colour: the colour mentioned, or null if not specified
- fit_style: fit/style description (e.g. "slim", "oversized", "minimalist"), or null
- material: material mentioned (e.g. "leather", "cotton", "denim"), or null
- gender: target gender/audience if mentioned, or null
- budget_hint: any price range or budget mentioned, or null
- season: season/occasion if mentioned, or null
- brand: specific brand name if mentioned, or null
- model_name: specific model/product name if mentioned, or null
- is_specific: true ONLY if both brand AND model are named (e.g. "Nike Air Force 1"), false otherwise
- source_text: the exact phrase from the input that describes this item
- search_query: a search query optimised for Google Shopping (combine key attributes)

Rules:
- Only extract items that are buyable products. Skip advice, opinions, styling tips.
- Never invent attributes not present in the text. If colour isn't mentioned, colour is null.
- The user's own messages may appear mixed in — only extract items from the AI's recommendations.
- Return a JSON array of objects. No markdown, no explanation, just the JSON array.
```

- [ ] **Step 3: Write failing tests for parser**

```python
# backend/tests/test_parser.py
import pytest
from app.models import ParsedItem

def test_parsed_item_specific():
    item = ParsedItem(
        category="sneakers", brand="Nike", model_name="Air Force 1",
        is_specific=True, source_text="Nike Air Force 1",
        search_query="Nike Air Force 1 sneakers"
    )
    assert item.is_specific is True
    assert item.brand == "Nike"

def test_parsed_item_generic():
    item = ParsedItem(
        category="sneakers", colour="white", material="leather",
        is_specific=False, source_text="white leather sneakers",
        search_query="white leather sneakers"
    )
    assert item.is_specific is False
    assert item.brand is None
```

- [ ] **Step 4: Run tests — should pass (model only)**

- [ ] **Step 5: Implement parser.py**

```python
# backend/app/parser.py
import json
from openai import AsyncOpenAI
from app.models import ParsedItem, ParseResult
from pathlib import Path

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "parse_chat.txt"

async def parse_chat(text: str, api_key: str, model: str = "gpt-4o-mini") -> ParseResult:
    if not text.strip():
        return ParseResult(items=[], raw_input_length=0, parse_model=model)

    system_prompt = PROMPT_PATH.read_text()
    client = AsyncOpenAI(api_key=api_key)

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text[:10000]},  # Cap input length
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
    )

    raw = response.choices[0].message.content
    parsed = json.loads(raw)
    items_data = parsed if isinstance(parsed, list) else parsed.get("items", [])
    items = [ParsedItem(**item) for item in items_data]

    return ParseResult(items=items, raw_input_length=len(text), parse_model=model)
```

- [ ] **Step 6: Add integration test (requires API key)**

```python
# backend/tests/test_parser_integration.py
import pytest, asyncio, os
from app.parser import parse_chat

SAMPLE_CHAT = """
AI: Here's a casual summer outfit I'd recommend:
1. White leather sneakers - minimalist design, versatile
2. A beige linen overshirt - relaxed fit, breathable
3. Slim dark navy chinos - tapered leg
4. A simple brown leather belt
"""

@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="No API key")
def test_parse_sample_chat():
    result = asyncio.run(parse_chat(SAMPLE_CHAT, os.getenv("OPENAI_API_KEY")))
    assert len(result.items) >= 3
    assert any("sneaker" in item.category.lower() for item in result.items)
```

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: LLM-powered chat parser with structured item extraction"
```

---

### Task 4: Product Finder (SerpApi Google Shopping Discovery)

**Files:**
- Create: `backend/app/finder.py`
- Create: `backend/tests/test_finder.py`

**Interfaces:**
- Consumes: `SerpApiClient.search()`, `ParsedItem`
- Produces: `ProductCandidate` model — `title`, `price`, `extracted_price`, `currency`, `source`, `link`, `thumbnail`, `rating`, `reviews`, `product_id`, `engine_used`, `position`
- Produces: `async find_products(item: ParsedItem, client: SerpApiClient, market: str) -> list[ProductCandidate]`

- [ ] **Step 1: Add ProductCandidate to models.py**

```python
# Add to backend/app/models.py
class ProductCandidate(BaseModel):
    title: str
    price: Optional[str] = None
    extracted_price: Optional[float] = None
    currency: str = "USD"
    source: str  # Seller/retailer name
    link: str
    thumbnail: Optional[str] = None
    rating: Optional[float] = None
    reviews: Optional[int] = None
    product_id: Optional[str] = None
    engine_used: str
    position: int
```

- [ ] **Step 2: Write failing tests**

```python
# backend/tests/test_finder.py
import pytest, asyncio
from app.finder import find_products, _build_shopping_params
from app.models import ParsedItem

def test_build_shopping_params_india():
    item = ParsedItem(
        category="sneakers", colour="white", material="leather",
        is_specific=False, source_text="white leather sneakers",
        search_query="white leather sneakers"
    )
    params = _build_shopping_params(item, market="in")
    assert params["q"] == "white leather sneakers"
    assert params["gl"] == "in"
    assert params["hl"] == "en"

def test_build_shopping_params_us():
    item = ParsedItem(
        category="sneakers", brand="Nike", model_name="Air Force 1",
        is_specific=True, source_text="Nike Air Force 1",
        search_query="Nike Air Force 1 sneakers"
    )
    params = _build_shopping_params(item, market="us")
    assert params["gl"] == "us"
```

- [ ] **Step 3: Run tests to verify they fail**

- [ ] **Step 4: Implement finder.py**

```python
# backend/app/finder.py
from app.models import ParsedItem, ProductCandidate
from app.serpapi_client import SerpApiClient

def _build_shopping_params(item: ParsedItem, market: str = "in") -> dict:
    params = {
        "q": item.search_query,
        "gl": market,
        "hl": "en",
        "num": 10,
    }
    if market == "in":
        params["google_domain"] = "google.co.in"
    return params

async def find_products(
    item: ParsedItem,
    client: SerpApiClient,
    market: str = "in",
) -> list[ProductCandidate]:
    params = _build_shopping_params(item, market)
    data = await client.search("google_shopping", params)

    candidates = []
    for result in data.get("shopping_results", [])[:10]:
        currency = "INR" if market == "in" else "USD"
        candidates.append(ProductCandidate(
            title=result.get("title", "Unknown"),
            price=result.get("price"),
            extracted_price=result.get("extracted_price"),
            currency=currency,
            source=result.get("source", "Unknown"),
            link=result.get("link", ""),
            thumbnail=result.get("thumbnail"),
            rating=result.get("rating"),
            reviews=result.get("reviews"),
            product_id=result.get("product_id"),
            engine_used="google_shopping",
            position=result.get("position", 0),
        ))
    return candidates
```

- [ ] **Step 5: Run tests to verify they pass**

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: product finder via Google Shopping API"
```

---

### Task 5: Confidence Scorer / Verifier

**Files:**
- Create: `backend/app/verifier.py`
- Create: `backend/tests/test_verifier.py`

**Interfaces:**
- Consumes: `ParsedItem`, `ProductCandidate`
- Produces: `AttributeScore` — `attribute`, `match: bool`, `confidence: float`, `evidence: str`
- Produces: `VerificationResult` — `overall_confidence: float`, `scores: list[AttributeScore]`, `label: str` (Exact/Variant/Best match)
- Produces: `verify_match(item: ParsedItem, candidate: ProductCandidate) -> VerificationResult`

- [ ] **Step 1: Add verification models to models.py**

```python
# Add to backend/app/models.py
class AttributeScore(BaseModel):
    attribute: str  # e.g. "colour", "category", "brand", "material"
    match: bool
    confidence: float  # 0.0-1.0
    evidence: str  # Why this score

class VerificationResult(BaseModel):
    overall_confidence: float
    scores: list[AttributeScore]
    label: str  # "Exact", "Variant", "Best match to your description"
```

- [ ] **Step 2: Write failing tests for verifier**

```python
# backend/tests/test_verifier.py
import pytest
from app.verifier import verify_match
from app.models import ParsedItem, ProductCandidate

def test_exact_brand_match():
    item = ParsedItem(
        category="sneakers", brand="Nike", model_name="Air Force 1",
        is_specific=True, source_text="Nike Air Force 1",
        search_query="Nike Air Force 1"
    )
    candidate = ProductCandidate(
        title="Nike Air Force 1 '07 White Sneakers",
        price="$110", extracted_price=110.0, currency="USD",
        source="Nike.com", link="https://nike.com/af1",
        engine_used="google_shopping", position=1
    )
    result = verify_match(item, candidate)
    assert result.label == "Exact"
    assert result.overall_confidence >= 0.8

def test_generic_match():
    item = ParsedItem(
        category="sneakers", colour="white", material="leather",
        is_specific=False, source_text="white leather sneakers",
        search_query="white leather sneakers"
    )
    candidate = ProductCandidate(
        title="Adidas Stan Smith White Leather Sneaker",
        price="$85", extracted_price=85.0, currency="USD",
        source="Amazon", link="https://amazon.com/...",
        engine_used="google_shopping", position=1
    )
    result = verify_match(item, candidate)
    assert result.label == "Best match to your description"
    assert result.overall_confidence > 0.5

def test_poor_match_low_confidence():
    item = ParsedItem(
        category="chinos", colour="navy", fit_style="slim",
        is_specific=False, source_text="slim navy chinos",
        search_query="slim navy chinos"
    )
    candidate = ProductCandidate(
        title="Red Cargo Pants Wide Leg",
        price="$40", extracted_price=40.0, currency="USD",
        source="Shein", link="https://shein.com/...",
        engine_used="google_shopping", position=8
    )
    result = verify_match(item, candidate)
    assert result.overall_confidence < 0.4
```

- [ ] **Step 3: Run tests to verify they fail**

- [ ] **Step 4: Implement verifier.py**

```python
# backend/app/verifier.py
from app.models import ParsedItem, ProductCandidate, AttributeScore, VerificationResult

def _check_attribute(name: str, expected: str | None, title: str) -> AttributeScore:
    """Check if an expected attribute appears in the product title."""
    if expected is None:
        return AttributeScore(attribute=name, match=True, confidence=1.0, evidence="Not specified in request")

    title_lower = title.lower()
    expected_lower = expected.lower()

    # Direct substring match
    if expected_lower in title_lower:
        return AttributeScore(attribute=name, match=True, confidence=0.95, evidence=f"'{expected}' found in title")

    # Synonym/fuzzy matching for common attributes
    synonyms = {
        "navy": ["dark blue", "navy blue"],
        "white": ["ivory", "off-white", "cream"],
        "black": ["onyx", "jet black"],
        "sneakers": ["shoes", "trainers", "kicks"],
        "chinos": ["pants", "trousers"],
        "overshirt": ["shirt jacket", "shacket", "over shirt"],
        "slim": ["skinny", "tapered", "fitted"],
        "leather": ["faux leather", "pu leather", "genuine leather"],
    }

    for synonym in synonyms.get(expected_lower, []):
        if synonym in title_lower:
            return AttributeScore(attribute=name, match=True, confidence=0.8, evidence=f"Synonym '{synonym}' found")

    return AttributeScore(attribute=name, match=False, confidence=0.1, evidence=f"'{expected}' not found in title")


def verify_match(item: ParsedItem, candidate: ProductCandidate) -> VerificationResult:
    scores = []

    # Check category
    scores.append(_check_attribute("category", item.category, candidate.title))

    # Check colour
    if item.colour:
        scores.append(_check_attribute("colour", item.colour, candidate.title))

    # Check brand
    if item.brand:
        scores.append(_check_attribute("brand", item.brand, candidate.title))

    # Check model name
    if item.model_name:
        scores.append(_check_attribute("model", item.model_name, candidate.title))

    # Check material
    if item.material:
        scores.append(_check_attribute("material", item.material, candidate.title))

    # Check fit/style
    if item.fit_style:
        scores.append(_check_attribute("fit_style", item.fit_style, candidate.title))

    # Check price band if budget hint given
    if item.budget_hint and candidate.extracted_price:
        scores.append(_check_price_band(item.budget_hint, candidate.extracted_price))

    # Calculate overall confidence
    if scores:
        overall = sum(s.confidence for s in scores) / len(scores)
    else:
        overall = 0.5

    # Determine label
    if item.is_specific:
        brand_ok = any(s.attribute == "brand" and s.match for s in scores)
        model_ok = any(s.attribute == "model" and s.match for s in scores)
        if brand_ok and model_ok:
            label = "Exact"
        elif brand_ok:
            label = "Variant"
        else:
            label = "Best match to your description"
    else:
        label = "Best match to your description"

    return VerificationResult(overall_confidence=round(overall, 3), scores=scores, label=label)


def _check_price_band(budget_hint: str, price: float) -> AttributeScore:
    """Check if price falls within the budget hint."""
    # Simple heuristic: extract numbers from budget hint
    import re
    numbers = re.findall(r'\d+', budget_hint)
    if not numbers:
        return AttributeScore(attribute="price_band", match=True, confidence=0.5, evidence="Could not parse budget")

    if len(numbers) == 1:
        target = float(numbers[0])
        ratio = min(price, target) / max(price, target) if max(price, target) > 0 else 0
        match = ratio > 0.5
        return AttributeScore(attribute="price_band", match=match, confidence=ratio, evidence=f"Price {price} vs budget ~{target}")
    else:
        low, high = float(numbers[0]), float(numbers[1])
        match = low <= price <= high
        confidence = 0.9 if match else 0.2
        return AttributeScore(attribute="price_band", match=match, confidence=confidence, evidence=f"Price {price} vs range {low}-{high}")
```

- [ ] **Step 5: Run tests to verify they pass**

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: per-attribute confidence verifier with honest labelling"
```

---

### Task 6: SSE Streaming API Endpoint

**Files:**
- Create: `backend/app/api.py`
- Modify: `backend/app/main.py` (add router)
- Create: `backend/tests/test_api.py`

**Interfaces:**
- Consumes: `parse_chat()`, `find_products()`, `verify_match()`, `SerpApiClient`
- Produces: `POST /api/search` — accepts chat text, streams SSE events (item_parsed, product_found, search_complete, trace_event)
- Produces: SSE event types: `item_parsed`, `product_found`, `trace`, `error`, `complete`

- [ ] **Step 1: Define SSE event models**

```python
# Add to backend/app/models.py
class SSEEvent(BaseModel):
    event: str  # "item_parsed", "product_found", "trace", "error", "complete"
    data: dict

class SearchRequest(BaseModel):
    chat_text: str
    market: str = "in"

class ProductResult(BaseModel):
    item: ParsedItem
    candidates: list[ProductCandidate]
    verifications: list[VerificationResult]
```

- [ ] **Step 2: Implement api.py with SSE streaming**

```python
# backend/app/api.py
import json, asyncio
from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse
from app.models import SearchRequest, ParsedItem
from app.parser import parse_chat
from app.finder import find_products
from app.verifier import verify_match
from app.serpapi_client import SerpApiClient
from app.config import Settings

router = APIRouter(prefix="/api")
settings = Settings()

@router.post("/search")
async def search(request: SearchRequest):
    async def event_generator():
        client = SerpApiClient(
            api_key=settings.serpapi_api_key,
            cache_db=settings.cache_db_path,
            max_calls=settings.max_calls_per_session,
        )

        # Step 1: Parse
        yield {"event": "trace", "data": json.dumps({"agent": "parser", "action": "Parsing chat input", "engine": "OpenAI GPT-4o-mini"})}

        try:
            parse_result = await parse_chat(request.chat_text, settings.openai_api_key, settings.openai_model_parse)
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"message": f"Parse failed: {str(e)}"})}
            return

        for item in parse_result.items:
            yield {"event": "item_parsed", "data": item.model_dump_json()}

        # Step 2: Find products for each item
        for item in parse_result.items:
            yield {"event": "trace", "data": json.dumps({
                "agent": "finder", "action": f"Searching for: {item.search_query}",
                "engine": "Google Shopping", "market": request.market
            })}

            try:
                candidates = await find_products(item, client, request.market)
            except Exception as e:
                yield {"event": "error", "data": json.dumps({"message": f"Search failed for {item.category}: {str(e)}"})}
                candidates = []

            # Step 3: Verify each candidate
            verified = []
            for candidate in candidates[:5]:  # Top 5 only
                verification = verify_match(item, candidate)
                verified.append({
                    "candidate": candidate.model_dump(),
                    "verification": verification.model_dump(),
                })

            # Sort by confidence
            verified.sort(key=lambda v: v["verification"]["overall_confidence"], reverse=True)

            yield {"event": "product_found", "data": json.dumps({
                "item": item.model_dump(),
                "results": verified,
            })}

        yield {"event": "complete", "data": json.dumps({
            "total_items": len(parse_result.items),
            "serpapi_calls": client.get_call_count(),
            "call_log": client.get_call_log(),
        })}

    return EventSourceResponse(event_generator())
```

- [ ] **Step 3: Wire router into main.py**

```python
# Add to backend/app/main.py
from app.api import router
app.include_router(router)
```

- [ ] **Step 4: Test with curl**

```bash
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{"chat_text": "Get white leather sneakers and navy slim chinos", "market": "in"}'
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: SSE streaming search endpoint with progressive results"
```

---

### Task 7: Compare-Prices Subagent

**Files:**
- Create: `backend/app/compare.py`
- Create: `backend/tests/test_compare.py`
- Modify: `backend/app/api.py` (add compare endpoint)

**Interfaces:**
- Consumes: `SerpApiClient`, `ProductCandidate`, `verify_match()`
- Produces: `CompareResult` model — `offers: list[CompareOffer]`, `cheapest_index: int`
- Produces: `CompareOffer` — `platform`, `seller`, `price`, `extracted_price`, `currency`, `link`, `verified: bool`, `verification: VerificationResult`, `shipping_info: str | None`
- Produces: `POST /api/compare` — accepts product details, streams comparison results

- [ ] **Step 1: Add compare models to models.py**

```python
# Add to backend/app/models.py
class CompareOffer(BaseModel):
    platform: str
    seller: str
    price: Optional[str] = None
    extracted_price: Optional[float] = None
    currency: str = "USD"
    link: str
    verified: bool = False
    verification: Optional[VerificationResult] = None
    shipping_info: Optional[str] = None

class CompareRequest(BaseModel):
    product_title: str
    product_attributes: dict
    product_image: Optional[str] = None
    market: str = "in"

class CompareResult(BaseModel):
    offers: list[CompareOffer]
    cheapest_index: Optional[int] = None
    search_engines_used: list[str]
```

- [ ] **Step 2: Write failing tests**

```python
# backend/tests/test_compare.py
import pytest
from app.compare import _build_compare_queries

def test_build_compare_queries_india():
    queries = _build_compare_queries("Nike Air Force 1 White", {"brand": "Nike"}, "in")
    assert any("google_shopping" in q["engine"] for q in queries)
    assert any("amazon" in q["engine"] for q in queries)

def test_build_compare_queries_us():
    queries = _build_compare_queries("Nike Air Force 1 White", {"brand": "Nike"}, "us")
    assert any("walmart" in q["engine"] for q in queries)
```

- [ ] **Step 3: Run tests to verify they fail**

- [ ] **Step 4: Implement compare.py**

```python
# backend/app/compare.py
import asyncio
from app.models import CompareOffer, CompareResult, ParsedItem, ProductCandidate, VerificationResult
from app.serpapi_client import SerpApiClient
from app.verifier import verify_match

def _build_compare_queries(title: str, attributes: dict, market: str) -> list[dict]:
    """Build search queries for different platforms."""
    # Clean title for searching
    search_term = title[:80]
    queries = []

    # Google Shopping (different query angle)
    params_gs = {"q": search_term, "gl": market, "hl": "en", "num": 5}
    if market == "in":
        params_gs["google_domain"] = "google.co.in"
    queries.append({"engine": "google_shopping", "params": params_gs})

    # Amazon
    amazon_domain = "amazon.in" if market == "in" else "amazon.com"
    queries.append({"engine": "amazon", "params": {"search_term": search_term, "amazon_domain": amazon_domain}})

    # eBay (global)
    queries.append({"engine": "ebay", "params": {"_nkw": search_term, "ebay_domain": "ebay.com"}})

    if market == "us":
        # Walmart (US only)
        queries.append({"engine": "walmart", "params": {"query": search_term}})

    return queries


async def compare_prices(
    product_title: str,
    product_attributes: dict,
    client: SerpApiClient,
    market: str = "in",
) -> CompareResult:
    queries = _build_compare_queries(product_title, product_attributes, market)
    offers: list[CompareOffer] = []
    engines_used = []

    # Build a ParsedItem from the product for verification
    ref_item = ParsedItem(
        category=product_attributes.get("category", "product"),
        brand=product_attributes.get("brand"),
        model_name=product_attributes.get("model"),
        colour=product_attributes.get("colour"),
        material=product_attributes.get("material"),
        is_specific=bool(product_attributes.get("brand")),
        source_text=product_title,
        search_query=product_title,
    )

    for query in queries:
        engine = query["engine"]
        engines_used.append(engine)

        try:
            data = await client.search(engine, query["params"])
        except Exception:
            continue

        # Extract results based on engine
        results = _extract_results(engine, data)

        for r in results[:3]:  # Top 3 per platform
            candidate = ProductCandidate(
                title=r.get("title", ""),
                price=r.get("price"),
                extracted_price=r.get("extracted_price"),
                currency="INR" if market == "in" else "USD",
                source=r.get("source", r.get("seller", engine)),
                link=r.get("link", ""),
                thumbnail=r.get("thumbnail"),
                engine_used=engine,
                position=r.get("position", 0),
            )

            verification = verify_match(ref_item, candidate)

            # Only include if verification is reasonable
            if verification.overall_confidence >= 0.4:
                offers.append(CompareOffer(
                    platform=engine.replace("_", " ").title(),
                    seller=candidate.source,
                    price=candidate.price,
                    extracted_price=candidate.extracted_price,
                    currency=candidate.currency,
                    link=candidate.link,
                    verified=verification.overall_confidence >= 0.6,
                    verification=verification,
                ))

    # Sort by price (cheapest first), handling None prices
    offers_with_price = [o for o in offers if o.extracted_price is not None]
    offers_without_price = [o for o in offers if o.extracted_price is None]
    offers_with_price.sort(key=lambda o: o.extracted_price)
    all_offers = offers_with_price + offers_without_price

    cheapest = 0 if offers_with_price else None

    return CompareResult(offers=all_offers, cheapest_index=cheapest, search_engines_used=engines_used)


def _extract_results(engine: str, data: dict) -> list[dict]:
    """Extract product results from different engine response formats."""
    if engine == "google_shopping":
        return data.get("shopping_results", [])
    elif engine == "amazon":
        return data.get("organic_results", [])
    elif engine == "ebay":
        return data.get("organic_results", [])
    elif engine == "walmart":
        return data.get("organic_results", [])
    return []
```

- [ ] **Step 5: Add compare SSE endpoint to api.py**

```python
# Add to backend/app/api.py
@router.post("/compare")
async def compare(request: CompareRequest):
    async def event_generator():
        client = SerpApiClient(
            api_key=settings.serpapi_api_key,
            cache_db=settings.cache_db_path,
            max_calls=settings.max_calls_per_compare,
        )

        yield {"event": "trace", "data": json.dumps({
            "agent": "compare-prices",
            "action": f"Comparing prices for: {request.product_title}",
            "engine": "Multi-platform",
        })}

        try:
            result = await compare_prices(
                request.product_title,
                request.product_attributes,
                client,
                request.market,
            )
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"message": str(e)})}
            return

        yield {"event": "compare_complete", "data": json.dumps(result.model_dump())}

    return EventSourceResponse(event_generator())
```

- [ ] **Step 6: Run tests to verify they pass**

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: compare-prices subagent across Google Shopping, Amazon, eBay"
```

---

### Task 8: Frontend — Landing Page and Input

**Files:**
- Create/Modify: `frontend/src/app/page.tsx`
- Create: `frontend/src/app/globals.css` (design system)
- Create: `frontend/src/components/ChatInput.tsx`
- Create: `frontend/src/components/ExampleLoader.tsx`

**Interfaces:**
- Produces: Landing page with paste area, example chat loader, and "Find Products" button
- Produces: Design system CSS with colour palette, typography, spacing

- [ ] **Step 1: Create design system in globals.css**

Create a premium dark-theme design system with vibrant accent colours, glassmorphism, smooth transitions. Include CSS custom properties for all tokens.

- [ ] **Step 2: Create ChatInput component**

Large textarea with character count, clear button, paste detection. Handles empty/too-long gracefully.

- [ ] **Step 3: Create ExampleLoader component**

Three pre-built example chats the user can click to auto-fill. Uses realistic AI style advice format.

- [ ] **Step 4: Build landing page**

Hero section with one-line pitch, ChatInput, ExampleLoader, and "Find Products" CTA button. First impression in 5 seconds.

- [ ] **Step 5: Verify in browser**

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: landing page with chat input and example loader"
```

---

### Task 9: Frontend — Results Display with Streaming

**Files:**
- Create: `frontend/src/components/ProductCard.tsx`
- Create: `frontend/src/components/ConfidenceBadge.tsx`
- Create: `frontend/src/components/AttributeBreakdown.tsx`
- Create: `frontend/src/components/ItemSection.tsx`
- Create: `frontend/src/app/results/page.tsx`
- Create: `frontend/src/lib/api.ts`
- Create: `frontend/src/lib/useSearch.ts`

**Interfaces:**
- Consumes: SSE events from `/api/search`
- Produces: Streaming results page — items appear progressively, cards animate in
- Produces: ProductCard with image, title, price, seller, confidence badge, label
- Produces: ConfidenceBadge — colour-coded, click/hover reveals breakdown
- Produces: AttributeBreakdown — per-attribute match/miss with evidence

- [ ] **Step 1: Create API client with SSE handling**

```typescript
// frontend/src/lib/api.ts
export async function* streamSearch(chatText: string, market: string) {
  const response = await fetch('http://localhost:8000/api/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chat_text: chatText, market }),
  });
  // SSE parsing logic
}
```

- [ ] **Step 2: Create useSearch hook for state management**

- [ ] **Step 3: Create ProductCard component**

Premium card with product image, title, price, seller badge, buy link, confidence badge, and "Compare Prices" button. Honest labels (Exact/Variant/Best match). No-results state.

- [ ] **Step 4: Create ConfidenceBadge and AttributeBreakdown**

Colour-coded confidence (green ≥80%, yellow 50-79%, red <50%). Click reveals per-attribute breakdown with ✓/✗ and evidence text.

- [ ] **Step 5: Create ItemSection — groups cards under each parsed item**

- [ ] **Step 6: Build results page with progressive loading**

Cards stream in with fade/slide animations as SSE events arrive. Loading skeleton while searching.

- [ ] **Step 7: Verify in browser with live search**

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: streaming results page with confidence badges"
```

---

### Task 10: Frontend — Agent Trace Panel

**Files:**
- Create: `frontend/src/components/TracePanel.tsx`
- Create: `frontend/src/components/TraceEvent.tsx`
- Modify: `frontend/src/app/results/page.tsx` (integrate trace)

**Interfaces:**
- Consumes: `trace` SSE events
- Produces: Side panel showing live agent activity — which agent, which engine, what action, outcome
- Produces: Animated entries, colour-coded by agent type

- [ ] **Step 1: Create TraceEvent component**

Timestamped entry showing agent icon, engine badge, action text, and status (searching/cached/complete/error).

- [ ] **Step 2: Create TracePanel**

Collapsible side panel, auto-scrolls to latest, shows [cached] label honestly.

- [ ] **Step 3: Integrate into results page**

- [ ] **Step 4: Verify trace updates live during search**

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: live agent trace panel"
```

---

### Task 11: Frontend — Compare Prices Flow

**Files:**
- Create: `frontend/src/components/CompareModal.tsx`
- Create: `frontend/src/components/CompareOffer.tsx`
- Create: `frontend/src/lib/useCompare.ts`

**Interfaces:**
- Consumes: `POST /api/compare` SSE stream
- Produces: Modal/drawer showing compare-prices results — visibly distinct from main search
- Produces: Price comparison table with cheapest highlighted, verification status per offer

- [ ] **Step 1: Create useCompare hook**

- [ ] **Step 2: Create CompareOffer component**

Per-offer card: platform icon, seller, price, verification badge, buy link. Cheapest highlighted.

- [ ] **Step 3: Create CompareModal**

Full-screen modal/drawer with its own trace panel. Shows compare agent progress. Clear "hand-off" visual from main search.

- [ ] **Step 4: Wire "Compare Prices" button on ProductCard to CompareModal**

- [ ] **Step 5: Verify compare flow end-to-end**

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: compare-prices modal with multi-platform results"
```

---

### Task 12: Demo Mode and Pre-Cached Scripted Chats

**Files:**
- Create: `backend/scripts/cache_demo_data.py`
- Create: `backend/demo_chats/casual_summer.txt`
- Create: `backend/demo_chats/formal_interview.txt`
- Create: `backend/demo_chats/streetwear_specific.txt`

**Interfaces:**
- Produces: 3 scripted demo chats that exercise different paths (generic, specific brand, mixed)
- Produces: Script to pre-populate cache by running all demo chats against live SerpApi
- Produces: Demo mode flag that ensures only cached results are used

- [ ] **Step 1: Write 3 demo chats**

1. **Casual Summer** (generic): white sneakers, linen shirt, chinos, sunglasses
2. **Formal Interview** (mixed): navy blazer, Oxford shirt, "Allen Edmonds" shoes (specific)
3. **Streetwear** (specific brands): "Nike Dunk Low", "Carhartt WIP" jacket, "Levi's 501"

- [ ] **Step 2: Create cache pre-population script**

```python
# backend/scripts/cache_demo_data.py
# Runs each demo chat through the full pipeline, populating the SQLite cache
```

- [ ] **Step 3: Add demo mode to config**

When `DEMO_MODE=true`, SerpApiClient only returns cached results and errors on cache miss.

- [ ] **Step 4: Run the cache script to populate demo data**

- [ ] **Step 5: Verify demo mode works without API keys**

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: demo mode with 3 pre-cached scripted chats"
```

---

### Task 13: Evaluation Harness

**Files:**
- Create: `eval/test_chats/` (20 test chats)
- Create: `eval/labels/` (human-labelled expected results)
- Create: `eval/run_eval.py`
- Create: `eval/report.md`

**Interfaces:**
- Produces: 20 test chat files (varied: casual, formal, gendered, neutral, specific, generic, messy)
- Produces: Evaluation script that measures: parse quality, top-1/top-3 match rate, confidence calibration, latency, SerpApi calls per run
- Produces: Evaluation report with tables and numbers

- [ ] **Step 1: Create 20 test chats**

Include deliberately difficult cases: messy formatting, emojis, multiple turns, irrelevant content, no shoppable items.

- [ ] **Step 2: Create labels for each chat**

JSON files with expected items and acceptable match criteria.

- [ ] **Step 3: Implement evaluation script**

```python
# eval/run_eval.py
# For each test chat:
# 1. Parse → check expected items extracted
# 2. Find → check top-1 and top-3 relevance
# 3. Verify → check confidence calibration (accuracy per confidence band)
# 4. Measure latency and API call count
```

- [ ] **Step 4: Run evaluation and generate report**

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: evaluation harness with 20 test chats and metrics"
```

---

### Task 14: Error States, Polish, and Responsive Design

**Files:**
- Modify: All frontend components (error states, loading states, empty states)
- Create: `frontend/src/components/ErrorBoundary.tsx`
- Create: `frontend/src/components/LoadingSkeleton.tsx`
- Modify: `frontend/src/app/globals.css` (responsive, dark/light, reduced motion)

**Interfaces:**
- Produces: Designed error, loading, empty, partial-result, and offline states
- Produces: Responsive layout (mobile + projector)
- Produces: Dark/light theme support
- Produces: Accessibility (contrast, focus, keyboard, alt text, reduced motion)

- [ ] **Step 1: Design and implement all error states**

- [ ] **Step 2: Add loading skeletons for progressive loading**

- [ ] **Step 3: Make layout responsive (mobile-first)**

- [ ] **Step 4: Add dark/light theme toggle**

- [ ] **Step 5: Accessibility audit and fixes**

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: error states, responsive design, accessibility"
```

---

### Task 15: Documentation, Deployment, and Demo Script

**Files:**
- Modify: `README.md` (full)
- Create: `docs/ARCHITECTURE.md`
- Create: `docs/DEMO_SCRIPT.md`
- Create: `docs/PITCH.md`
- Create: `docs/JUDGE_QA.md`
- Deployment configuration files

**Interfaces:**
- Produces: Complete README (problem, solution, architecture, SerpApi usage table, setup, limits, results)
- Produces: Architecture diagram (Mermaid)
- Produces: 90-second demo script
- Produces: Pitch outline
- Produces: Judge Q&A

- [ ] **Step 1: Write full README**

- [ ] **Step 2: Create architecture overview with Mermaid diagram**

- [ ] **Step 3: Write 90-second demo script**

- [ ] **Step 4: Write pitch outline**

Problem → Insight → Demo highlights → Numbers → What's next

- [ ] **Step 5: Write likely judge Q&A**

- [ ] **Step 6: Deploy backend to Render**

- [ ] **Step 7: Deploy frontend to Vercel**

- [ ] **Step 8: Verify deployed app works end-to-end**

- [ ] **Step 9: Final commit**

```bash
git add -A
git commit -m "docs: README, architecture, demo script, pitch, deployment"
```

---

## Task Dependency Graph

```
T1 (Scaffold) → T2 (SerpApi Client) → T3 (Parser) → T4 (Finder) → T5 (Verifier)
                                                                        ↓
T6 (SSE API) ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ┘
    ↓
T7 (Compare) → T8 (Frontend Landing) → T9 (Results) → T10 (Trace) → T11 (Compare UI)
                                                                          ↓
T12 (Demo Mode) → T13 (Eval) → T14 (Polish) → T15 (Deploy + Docs)
```

## Latency Targets

| Action | Target | Measurement |
|--------|--------|-------------|
| First result card visible | < 5 seconds | From button press to first ProductCard rendered |
| Full 5-item outfit results | < 30 seconds | All items have results |
| Compare results start streaming | < 3 seconds | From "Compare" click |
| Compare complete | < 15 seconds | All platforms searched |
