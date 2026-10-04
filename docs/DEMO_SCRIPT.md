# 90-Second Demo Script

## Setup (Before Demo)

- Backend running: `cd backend && uvicorn app.main:app --port 8000`
- Frontend running: `cd frontend && npm run dev`
- Open `http://localhost:3000` in Chrome (full screen, dark mode)
- Pre-fill nothing — start from blank state

---

## The Demo (90 seconds)

**[0:00] Hook — the problem (10s)**

> "You've had this experience: AI gives you a perfect outfit, but then you spend 20 minutes googling each item, unsure if what you found is what was meant."

**[0:10] Input — paste the chat (10s)**

Click **"☀️ Casual Summer"** example to auto-fill the textarea.

> "This is a real AI style advice conversation — 5 items, completely generic descriptions."

Hit **🔍 Find Products**.

**[0:20] Streaming — watch it work (30s)**

Point to the Agent Trace panel:

> "The trace panel shows you exactly what's happening. The parser extracts 5 structured items from the freeform text — white leather sneakers, beige linen overshirt, navy chinos, sunglasses, belt."

As cards appear:

> "Results stream in progressively. Each card has a confidence score — this is per-attribute, not just a vibes number."

Click the ▼ button on a product card:

> "Colour: found. Material: found. Category: sneakers matched. That's why it's 87% confident."

**[0:50] Compare prices (20s)**

Click **💰 Compare Prices** on the top sneaker result.

> "One click — we search Google Shopping, Amazon, and eBay for the same product simultaneously."

When results appear:

> "Three platforms, cheapest highlighted in green. Each offer is also verified against the original description — we only show you offers that actually match."

**[1:10] The key point (20s)**

Point to the footer call count:

> "This entire session — 5 items found, 1 compare — used N SerpApi calls. Everything is cached in SQLite. Run the same chat again: zero calls."

Scroll to the badge on one of the exact-match cards:

> "We never say 'Exact' unless we can prove it. Brand in title, model in title — then Exact. Otherwise it's honest: 'Best match to your description'."

**[1:30] Done.**

---

## Fallback: If the backend is slow

- Switch to the **"🔥 Streetwear"** example instead — Nike Dunk Low is usually cached
- If SSE stalls, refresh and use market toggle to switch to US

## Things to Highlight if Asked

- Cache: "Every SerpApi call is cached. Identical searches across sessions are free."
- LLM: "Claude Haiku via AWS Bedrock — fast, cheap, structured JSON output."
- Honesty: "We never fabricate. If a price isn't available, we say 'Price unavailable'. If confidence is low, the badge is red."
- India default: "The default market is India — gl=in, amazon.in. Switch to US in the header."
