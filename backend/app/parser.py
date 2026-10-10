"""LLM-powered chat parser: extracts shoppable items from AI style advice.

Uses Featherless AI (OpenAI-compatible API) with Qwen2.5-72B-Instruct.
JSON mode enforced via response_format to guarantee valid JSON every time.
"""

import asyncio
import json

import httpx

from app.models import ParsedItem, ParseResult
from pathlib import Path

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "parse_chat.txt"
MAX_INPUT_CHARS = 10_000
MODEL_NAME = "Qwen/Qwen2.5-72B-Instruct"
FEATHERLESS_BASE_URL = "https://api.featherless.ai/v1"


async def parse_chat(
    text: str,
    featherless_api_key: str,
    audience: str,           # "male" or "female" — mandatory, injected into system prompt
    model: str = MODEL_NAME,
) -> ParseResult:
    """
    Parse a pasted AI chat and extract shoppable items using Qwen2.5-72B-Instruct
    via the Featherless OpenAI-compatible API.

    Returns a ParseResult with structured items and metadata.
    Handles empty input, over-long input, and malformed LLM output gracefully.
    """
    if not text or not text.strip():
        return ParseResult(items=[], raw_input_length=0, parse_model=model)

    truncated = text[:MAX_INPUT_CHARS]
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
    # Inject the audience into the prompt before sending to LLM
    system_prompt = system_prompt.replace("{audience}", audience)


    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": truncated},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
        "max_tokens": 2048,
    }

    headers = {
        "Authorization": f"Bearer {featherless_api_key}",
        "Content-Type": "application/json",
    }

    async def invoke() -> str:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{FEATHERLESS_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    try:
        # Retry once on rate-limit (429)
        for attempt in range(2):
            try:
                raw = await invoke()
                break
            except httpx.HTTPStatusError as exc:
                is_rate_limit = exc.response.status_code == 429
                if is_rate_limit and attempt == 0:
                    await asyncio.sleep(35)
                    continue
                elif is_rate_limit:
                    raise RuntimeError(
                        "Featherless API rate limit reached. Please wait 30 seconds and try again."
                    ) from exc
                raise  # non-rate-limit errors propagate immediately

        raw_clean = raw.strip()
        if raw_clean.startswith("```json"):
            raw_clean = raw_clean[7:]
        if raw_clean.startswith("```"):
            raw_clean = raw_clean[3:]
        if raw_clean.endswith("```"):
            raw_clean = raw_clean[:-3]
            
        parsed = json.loads(raw_clean.strip())

        # Handle both {"items": [...]} and bare [...]
        if isinstance(parsed, list):
            items_data = parsed
        elif isinstance(parsed, dict):
            items_data = parsed.get("items", [])
        else:
            items_data = []

        items = []
        for item_data in items_data:
            try:
                items.append(ParsedItem(**item_data))
            except Exception as e:
                print(f"Validation error for item {item_data}: {e}")
                continue

        return ParseResult(
            items=items,
            raw_input_length=len(text),
            parse_model=model,
        )

    except json.JSONDecodeError:
        return ParseResult(items=[], raw_input_length=len(text), parse_model=model)
    except RuntimeError:
        raise  # already a clean message (e.g. rate limit) — pass through as-is
    except Exception as e:
        raise RuntimeError(f"Chat parsing failed: {str(e)}") from e
