# Parser and SSE Streaming Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the LLM parser robust to any format by using a meaning-based prompt, and fix the UI's SSE reader to correctly parse chunked data without silently dropping events.

**Architecture:** 
1. The parser prompt is replaced to instruct the LLM to read the entire text for meaning rather than strict labels, supporting a new `origin` field to clarify where the item came from.
2. The frontend SSE stream is refactored to use the spec-compliant `eventsource-parser` library, ensuring boundaries and `\r\n` are parsed correctly across network chunks.

**Tech Stack:** Python, FastAPI, Next.js, TypeScript, `eventsource-parser`, Pytest.

## Global Constraints

- Never display a product the text did not mention or imply without clearly marking it as inferred. Never invent attributes.
- No silent failures anywhere in the pipeline. Every error path ends in either a visible state or a logged, countable event.
- Cost control: Respect existing caps (12 items max), and inferred items count toward caps.

---

### Task 1: Update Parser Models & Prompt

**Files:**
- Modify: `backend/app/models.py`
- Create/Modify: `backend/prompts/parse_chat.txt`
- Test: `backend/tests/test_parser.py`

**Interfaces:**
- Produces: `ParsedItem` will now include an `origin` string field (Literal: "stated", "recommended", "inferred"). 

- [ ] **Step 1: Write the failing tests for parser rules (14 cases)**
Write the 14 cases in `test_parser.py` testing `parse_chat` directly (mocked or opt-in live). Run to verify failure.
- [ ] **Step 2: Update `models.py`**
Add `origin: Literal["stated", "recommended", "inferred"]` to `ParsedItem` model with a default (e.g. "stated") so old code doesn't break.
- [ ] **Step 3: Replace `backend/prompts/parse_chat.txt`**
Use the provided new prompt text from the brief.
- [ ] **Step 4: Run tests to verify they pass**
Run `pytest backend/tests/test_parser.py -v`. Confirm all 14 cases pass. If any fail, improve the prompt.
- [ ] **Step 5: Commit**
`git add backend/app/models.py backend/prompts/parse_chat.txt backend/tests/test_parser.py`
`git commit -m "fix(backend): liberalize parser prompt and add origin field"`

---

### Task 2: Backend Streaming Compliance

**Files:**
- Modify: `backend/app/api.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Produces: SSE stream endpoints with correct headers (`Cache-Control: no-cache`, `X-Accel-Buffering: no`, `Connection: keep-alive`). 

- [ ] **Step 1: Write the failing tests**
Write a quick test to ensure endpoints return correct SSE headers.
- [ ] **Step 2: Update API headers and error handling**
Ensure all streaming endpoints (`/api/search`, `/api/compare`, `/api/offline`) return the right headers. Ensure errors in parsing or elsewhere yield clean `event: error` SSE blocks instead of 500s.
- [ ] **Step 3: Run tests to verify they pass**
- [ ] **Step 4: Commit**
`git commit -m "fix(backend): add proxy-busting headers to SSE endpoints"`

---

### Task 3: Robust Frontend SSE Reader

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/src/lib/api.ts`
- Test: `frontend/src/lib/api.test.ts`

**Interfaces:**
- Consumes: The backend SSE endpoints.

- [ ] **Step 1: Install `eventsource-parser`**
Run `npm install eventsource-parser` in the frontend directory.
- [ ] **Step 2: Write failing reliability tests**
Write tests in `api.test.ts` for the SSE parsing logic (chunk splits, CRLF endings, multi-byte characters, malformed JSON, early end).
- [ ] **Step 3: Refactor `api.ts` streaming functions**
Replace the hand-rolled while loops in `streamSearch`, `streamCompare`, and `streamOffline` with `createParser` from `eventsource-parser`. Handle stream completion, cancellation, and malformed JSON warnings.
- [ ] **Step 4: Verify tests pass**
- [ ] **Step 5: Commit**
`git commit -m "fix(frontend): replace brittle SSE parser with eventsource-parser"`

---

### Task 4: UI/UX Error States and Origin Badge

**Files:**
- Modify: `frontend/src/app/page.tsx`
- Modify: `frontend/src/components/ItemCard.tsx` (or equivalent)

**Interfaces:**
- Consumes: `ParsedItem` and SSE error events.

- [ ] **Step 1: Add Origin UI**
Add a subtle badge ("Suggested for you") to item cards where `origin === "inferred"`.
- [ ] **Step 2: Add Error/Empty States**
If `items.length === 0` after parsing, show: "We couldn't find anything to shop for in that text, try describing what you're looking for". If stream is interrupted/errors, show a clear warning or retry button.
- [ ] **Step 3: Test manually**
Run the frontend and test the formal interview chat, an empty string, and a broken server.
- [ ] **Step 4: Commit**
`git commit -m "feat(ui): add inferred badge and empty/error states"`

---

### Task 5: Documentation Update

**Files:**
- Modify: `README.md`
- Modify: `docs/DECISIONS.md`

- [ ] **Step 1: Update README.md**
Add notes on how input is interpreted (liberal parsing) and the new `origin` field.
- [ ] **Step 2: Commit**
`git commit -m "docs: document liberal parser rules and origin field"`
