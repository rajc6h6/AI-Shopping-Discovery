# Judge Q&A — Paste-to-Product

## SerpApi Usage

**Q: Which SerpApi engines do you use?**

`google_shopping` for product discovery (all markets), `amazon` (amazon.in / amazon.com), `ebay` (ebay.com), and `walmart` (US only) for price comparison.

**Q: How do you avoid duplicate API calls?**

Every SerpApi response is cached in SQLite by a SHA-256 hash of the normalised `{engine, sorted_params}` dict (with `api_key` stripped). Cache-first on every request. Identical queries across sessions are served from cache with zero live calls.

**Q: What are your call limits?**

- Session cap: 50 SerpApi calls total
- Per search item: 1 Google Shopping call
- Per compare request: up to 4 calls (1 per platform)
- All enforced in `SerpApiClient._check_cap()`

---

## LLM / Parsing

**Q: What LLM do you use for parsing?**

AWS Bedrock with Claude Haiku (`anthropic.claude-haiku-4-5-*`). Fast, cheap, structured output via JSON prefill. The prompt is versioned in `backend/prompts/parse_chat.txt`.

**Q: Why not use the SerpApi AI Agents for parsing?**

We use Bedrock directly for two reasons: (1) we need structured `ParsedItem` objects with specific fields, and (2) the parsing step has no need for search access — it's pure text extraction.

---

## Confidence / Honesty

**Q: How does the confidence score work?**

Pure Python title-matching — no LLM, no API call. We check each specified attribute (category, colour, brand, model, material, fit, price band) against the product title using direct substring matching and a synonym dictionary. Overall confidence is the average per-attribute score. Labels:

- **Exact**: brand AND model both found in title
- **Variant**: brand found, model not
- **Best match to your description**: no specific brand, or missing model

**Q: Could the confidence scores be wrong?**

Yes, title-matching is imperfect. We're explicit about this — the evidence text in the breakdown shows exactly why a score was given. A product titled differently from how it's described will get a lower score even if it's correct.

---

## Architecture

**Q: Why FastAPI + SSE instead of WebSockets?**

SSE is simpler for this use case — it's one-directional (server to client), works over standard HTTP, needs no handshake, and is natively supported in `fetch()` without libraries.

**Q: Why SQLite instead of Redis?**

Ponytail principle: SQLite is zero infrastructure, zero cost, zero configuration. For a hackathon demo with one server instance, it's the right tool. Redis would be needed if we had horizontal scaling.

**Q: What's the latency?**

- First result card: ~3-5s (parse ~2s + one SerpApi call ~1-2s)
- Full 5-item search: ~10-20s (sequential, one search per item)
- Compare: ~5-10s (3-4 parallel engines, but we await sequentially to respect caps)

---

## What's Next

- Parallel item searches (currently sequential to simplify call counting)
- Image-based search: paste a screenshot, not just a text chat
- Price history tracking via the cache timestamps
- Personalisation: remember past searches, track favourite items
