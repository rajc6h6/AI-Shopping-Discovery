# Decisions Log — Paste-to-Product

Each entry: Options considered → Choice → Reason.

---

## D1: Application Architecture

**Options:**
1. Full-stack Python (FastAPI backend + Jinja templates)
2. Python backend (FastAPI) + React/Next.js frontend
3. Python backend (FastAPI) + Vanilla JS/HTML frontend (Vite)

**Choice:** Option 2 — **Next.js frontend + FastAPI backend**

**Reason:** The brief demands a premium, demo-ready UI with streaming results, live agent trace, progressive loading, and responsive design. Next.js gives us React's component model, SSE/streaming support, and easy deployment (Vercel). FastAPI handles async SerpApi calls efficiently with native SSE support. This is a hackathon — we need to move fast but look polished.

---

## D2: LLM Provider

**Options:**
1. OpenAI (GPT-4o / GPT-4o-mini)
2. Google Gemini
3. Anthropic Claude via AWS Bedrock

**Choice:** **Anthropic Claude via AWS Bedrock** — Claude 3 Haiku for parsing (cheap, fast, structured outputs)

**Reason:** The user requested Bedrock. Claude 3 Haiku is incredibly fast, handles structured outputs well, and is extremely cost-effective for large volumes of parsing. Claude 3.5 Sonnet can be used if higher reasoning is needed. Provider-agnostic interface means we can swap later.

---

## D3: SerpApi Access Method

**Options:**
1. Use `serpapi-search-tools` Python package
2. Use `google-search-results` official Python client
3. Direct HTTP calls via `httpx`

**Choice:** **Direct HTTP calls via `httpx`** with thin wrapper

**Reason:** We need raw JSON responses for verification scoring, fine-grained caching by normalised request, and access to engines (Immersive Product, Lens) that aren't exposed by the search-tools package. Also better for tracing (we control every call).

---

## D4: Caching Strategy

**Options:**
1. In-memory dict (lost on restart)
2. SQLite file-based cache
3. Redis
4. JSON files on disk

**Choice:** **SQLite file-based cache**

**Reason:** Persistent across restarts (critical for demo mode), zero infrastructure, fast enough, supports normalised request key lookup. Single file, easy to ship with the demo. Can pre-populate with scripted demo data.

---

## D5: Frontend Framework Details

**Options:**
1. Next.js App Router (React Server Components)
2. Next.js Pages Router (traditional)
3. Vite + React

**Choice:** **Next.js App Router** with client components for interactive parts

**Reason:** App Router is the modern default, gives us server components for initial render, client components for streaming/interactivity. Deploys to Vercel trivially. RSC not critical here — mostly client-side interactivity.

---

## D6: Streaming Protocol (Backend → Frontend)

**Options:**
1. WebSocket
2. Server-Sent Events (SSE)
3. Polling

**Choice:** **Server-Sent Events (SSE)**

**Reason:** Unidirectional (server→client) is all we need for progressive results and agent trace. Simpler than WebSocket, works through proxies, native browser support via EventSource. FastAPI has excellent SSE support via `sse-starlette`.

---

## D7: Confidence Scoring Approach

**Options:**
1. Simple keyword overlap scoring
2. LLM-based scoring (send product + item to LLM)
3. Hybrid: rule-based attribute matching + LLM fallback for ambiguous cases

**Choice:** **Option 3 — Hybrid**

**Reason:** Rule-based scoring for known attributes (colour, category, brand, material, price band) is deterministic, fast, free, and calibratable. LLM only needed for ambiguous cases or image-based verification (P1). This keeps costs down and makes calibration tractable.

---

## D8: Hosting / Deployment

**Options:**
1. Vercel (frontend) + Railway (backend)
2. Vercel (frontend) + Render (backend)
3. All-in-one on Render
4. Docker on any VPS

**Choice:** **Vercel (frontend) + Render (backend)**

**Reason:** Vercel is free-tier and optimised for Next.js. Render has free-tier for Python web services. Both have simple deploy-from-git. No Docker complexity needed for a hackathon.

---

## D9: India Market Handling

**Options:**
1. Default to US market, offer India as option
2. Default to India market
3. Auto-detect based on user location

**Choice:** **Default to India (`gl=in`, `amazon.in`)**, with option to switch to US

**Reason:** Builder is India-based, judges may be too. Google Shopping works with `gl=in` and returns INR. Amazon India works. Flipkart/Myntra not available — state this honestly in UI. US mode uses broader engine set (Walmart, eBay, etc.).

---

## D10: Demo Mode Implementation

**Options:**
1. Record and replay full HTTP responses
2. Pre-cached SerpApi responses in SQLite, UI reads from cache
3. Hardcoded mock data

**Choice:** **Option 2 — Pre-cached SerpApi responses in SQLite**

**Reason:** The same cache used for development doubles as demo mode storage. No separate mock layer needed. The cache key is the normalised request — if the exact request was made before, it's served from cache. Demo scripts just ensure those requests have been made once. Trace panel shows "[cached]" honestly.

---

## D11: Treat Brief as Approved Spec (Brainstorming Bypass)

**Options:**
1. Run full brainstorming skill with interactive Q&A
2. Treat the 11-section brief as the approved spec

**Choice:** **Option 2** — brief IS the spec

**Reason:** The brief explicitly says "Interpret intent; do not stop to ask me questions you can reasonably decide yourself" and "proceed into building without waiting." It contains complete requirements, constraints, success criteria, and priorities. Running brainstorming would stall progress on a task that's already fully specified. Record this decision and proceed directly to planning.

---

## D12: Monorepo vs Separate Repos

**Options:**
1. Monorepo with `frontend/` and `backend/` directories
2. Separate repos

**Choice:** **Monorepo**

**Reason:** Single repo, single deploy, easier for hackathon judges to clone and run. `frontend/` (Next.js) and `backend/` (FastAPI) at root level.

---

## D13: Parser Agent Design

**Options:**
1. Single LLM call with complex prompt
2. Two-stage: extract items → enrich each item
3. Chain-of-thought with structured output

**Choice:** **Option 1 — Single LLM call with structured output (JSON mode)**

**Reason:** GPT-4o-mini handles this well in one shot with a good system prompt and JSON schema. Two-stage adds latency and cost for minimal quality gain on fashion items. If parsing quality is poor, we can add a second pass as refinement.

---

## D14: SSE Stream Parsing Library

**Options:**
1. Write a custom `SSEReader` class that handles buffering, chunking, and CRLF edge cases natively.
2. Use an industry-standard library like `eventsource-parser`.

**Choice:** **Option 2 — `eventsource-parser`**

**Reason:** SSE edge cases (CRLF split across TCP chunks, comment keepalives, multi-line data, multi-byte character splitting) are notoriously difficult to hand-roll correctly without introducing subtle bugs. `eventsource-parser` is tiny, spec-compliant, and handles all buffering natively. It keeps our codebase simple and robust (Ponytail compliant: use standard solutions rather than re-inventing complex state machines).

---

## D15: Parser Fallback UI & Origin Handling

**Options:**
1. Drop the `origin` field if downstream breaks.
2. Ensure full pipeline support for `origin` and show it gracefully in the UI. Empty results show a friendly error state.

**Choice:** **Option 2**

**Reason:** The brief mandates full support for the liberalized parser rules. `origin` must be passed to the UI to distinguish "inferred" items. A subtle badge "suggested for you" will be used. Empty results will show a specific, friendly CTA instead of a silent or ugly crash.

---

## D16: Format-Agnostic Parser Design

**Options:**
1. Fix the speaker-label allow-list in the old prompt (add "Me:" to the list of recognised user labels).
2. Discard speaker-label logic entirely; extract from meaning, not format.

**Choice:** **Option 2 — Meaning-first, format-agnostic extraction**

**Reason:** Option 1 is whack-a-mole — any new label format (markdown bold, numbered turns, "Assistant (GPT):", no labels at all) would require another patch. The root cause is that the prompt tried to understand format rather than meaning. The replacement prompt explicitly instructs the model to ignore speaker labels and instead infer intent from verb tense and context (recommended vs. rejected vs. owned). This is more robust, correctly handles all 14 regression cases, and is simpler (fewer rules).

---

## D17: Vitest v2 for Frontend Unit Tests

**Options:**
1. Jest (the traditional choice)
2. Vitest v2 (compatible with `@types/node@20` which the project already uses)
3. Vitest v5 (latest; requires `@types/node@22+`)

**Choice:** **Vitest v2**

**Reason:** The project has `@types/node@^20` as a devDependency and Next.js 16 pulls in `vite` with compatible peer deps. Vitest v5 has a conflicting peer on `@types/node@22+` which would require a major node types upgrade. Vitest v2 installs cleanly, runs in under 2 seconds, has an identical API surface to v5 for our use case, and doesn't require a Jest transform config for ESM packages like `eventsource-parser`.
