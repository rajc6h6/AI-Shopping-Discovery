# Paste-to-Product

**Paste any AI style advice chat → get real, buyable products with confidence scores and cross-platform price comparison.**

Built for the [SerpApi Hackathon](https://serpapi.com).

---

## The Problem

AI chatbots give great style advice but leave you to do all the shopping yourself. They say "white leather sneakers" — you spend 40 minutes on Google, unsure whether what you found actually matches. 

## The Solution

Paste the AI chat here. We:
1. **Extract** every shoppable item (powered by AWS Bedrock Claude Haiku)
2. **Find** real products via Google Shopping (SerpApi)
3. **Score** every result with a per-attribute confidence breakdown (Exact / Variant / Best match)
4. **Compare prices** across Google Shopping, Amazon, and eBay — without duplicating API calls

---

## Architecture

```
Paste chat text
       │
       ▼
  AWS Bedrock (Claude Haiku)
  → Structured ParsedItem list
       │
       ▼
  SerpApi: Google Shopping (per item)
  → ProductCandidate list (cached in SQLite)
       │
       ▼
  Confidence Verifier (pure Python, no API)
  → VerificationResult with per-attribute scores
       │
       ▼
  SSE stream → Next.js frontend (progressive cards)
       │
       ▼  [on "Compare Prices" click]
  SerpApi: Amazon + eBay + Google Shopping
  → Sorted by price, cheapest highlighted
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full Mermaid diagram.

---

## SerpApi Usage

| Endpoint | Engine | Calls Per |
|----------|--------|-----------|
| `/api/search` | `google_shopping` | 1 per parsed item |
| `/api/compare` | `google_shopping`, `amazon`, `ebay`, `walmart` | up to 4 |

**Hard limits:**
- Session cap: 50 calls
- Per-item: 2 discovery calls max
- Per-compare: 4 calls max
- All responses cached in SQLite — zero duplicate calls

**Default market:** India (`gl=in`, `google_domain=google.co.in`). Switchable to US.

---

## Setup

### Prerequisites

- Python 3.12+
- Node.js 18+
- SerpApi API key → [serpapi.com](https://serpapi.com)
- AWS credentials with Bedrock access (for Claude Haiku parsing)

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Mac/Linux

pip install -r requirements.txt

cp .env.example .env
# Edit .env with your keys

uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:3000
```

### Demo mode (no API keys needed after cache is pre-populated)

```bash
cd backend
python scripts/cache_demo_data.py  # run once with real keys
# Then set DEMO_MODE=true in .env
```

---

## Project Structure

```
serpapi/
├── backend/
│   ├── app/
│   │   ├── config.py          # Pydantic settings
│   │   ├── cache.py           # SQLite cache
│   │   ├── serpapi_client.py  # SerpApi HTTP client with caching + cap
│   │   ├── parser.py          # Bedrock LLM item extraction
│   │   ├── finder.py          # Google Shopping product discovery
│   │   ├── verifier.py        # Per-attribute confidence scoring
│   │   ├── compare.py         # Multi-platform price comparison
│   │   ├── api.py             # FastAPI SSE endpoints
│   │   └── models.py          # Pydantic data models
│   ├── prompts/parse_chat.txt # Versioned LLM prompt
│   ├── demo_chats/            # 3 scripted demo chats
│   ├── scripts/cache_demo_data.py
│   └── tests/                 # 27 unit tests
├── frontend/
│   └── src/
│       ├── app/
│       │   ├── page.tsx       # Single-page app (all UI)
│       │   ├── globals.css    # Design system tokens
│       │   └── page.module.css # Component styles
│       └── lib/
│           ├── api.ts         # SSE client + type defs
│           └── examples.ts    # 3 pre-written example chats
└── eval/                      # Evaluation harness
    ├── test_chats/            # 20 test chats
    ├── labels/                # Expected results
    └── run_eval.py            # Evaluation script
```

---

## Constraints

- No fabricated products, prices, images, or reviews
- "Exact" / "Variant" labels only with evidence from the product title
- All prompts in versioned files under `backend/prompts/`
- No secrets in code — all keys from environment variables

---

## Results

27/27 backend unit tests pass. The evaluation harness (`eval/run_eval.py`) measures parse quality, top-1/top-3 match rate, confidence calibration, and SerpApi efficiency across 20 test chats.
