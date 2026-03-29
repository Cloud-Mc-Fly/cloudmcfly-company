"""CloudMcFly Company - Reusable Claude API client.

Dual-model strategy: default (Sonnet) for fast tasks, complex (Opus) for deep analysis.
Async, with retry logic and structured JSON output support.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from anthropic import AsyncAnthropic, APIError, APITimeoutError

from config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton client
# ---------------------------------------------------------------------------

_client: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        if not settings.anthropic_api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set. Cannot call Claude API."
            )
        _client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


# ---------------------------------------------------------------------------
# JSON parsing helper
# ---------------------------------------------------------------------------

def parse_json_response(raw: str) -> dict[str, Any]:
    """Robustly parse JSON from Claude's response.

    Handles markdown fences, leading text, trailing text.
    """
    text = raw.strip()

    # Try to extract JSON from markdown code fences
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    # Try to find JSON object or array
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start = text.find(start_char)
        if start == -1:
            continue
        # Find matching closing bracket
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == start_char:
                depth += 1
            elif ch == end_char:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        break

    # Last resort: try parsing the whole thing
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Could not parse JSON from response: %.200s...", text)
        return {"raw_response": text}


# ---------------------------------------------------------------------------
# Main API call
# ---------------------------------------------------------------------------

async def call_claude(
    user_prompt: str,
    system_prompt: str = "",
    *,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    json_output: bool = False,
    complex_task: bool = False,
) -> str:
    """Call Claude API with configurable parameters.

    Args:
        user_prompt: The user message.
        system_prompt: System instruction for Claude.
        model: Override model. If None, uses default or complex based on flag.
        temperature: Override temperature. If None, uses settings default.
        max_tokens: Override max tokens. If None, uses settings default.
        json_output: If True, appends JSON instruction to system prompt.
        complex_task: If True, uses the complex model (Opus).

    Returns:
        Claude's text response.

    Raises:
        RuntimeError: If API key is missing.
        APIError: On API failures after retries.
    """
    client = _get_client()

    # Select model
    if model is None:
        model = (
            settings.claude_complex_model
            if complex_task
            else settings.claude_default_model
        )

    # Defaults
    if temperature is None:
        temperature = settings.claude_temperature
    if max_tokens is None:
        max_tokens = settings.claude_max_tokens

    # JSON mode instruction
    effective_system = system_prompt
    if json_output:
        effective_system += (
            "\n\nWICHTIG: Antworte ausschliesslich mit validem JSON. "
            "Kein erklaerenden Text vor oder nach dem JSON. "
            "Kein Markdown. Nur reines JSON."
        )

    # Retry loop (max 2 retries)
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = await client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=effective_system if effective_system else [],
                messages=[{"role": "user", "content": user_prompt}],
            )
            result = response.content[0].text.strip()
            logger.debug(
                "Claude response (%s, %d tokens): %.100s...",
                model,
                response.usage.output_tokens,
                result,
            )
            return result

        except APITimeoutError as e:
            last_error = e
            logger.warning(
                "Claude API timeout (attempt %d/3, model=%s)",
                attempt + 1,
                model,
            )
        except APIError as e:
            last_error = e
            if e.status_code == 529:  # Overloaded
                logger.warning(
                    "Claude API overloaded (attempt %d/3)", attempt + 1
                )
            elif e.status_code == 429:  # Rate limited
                logger.warning(
                    "Claude API rate limited (attempt %d/3)", attempt + 1
                )
            else:
                raise  # Non-retryable error

        # Wait before retry (simple backoff)
        if attempt < 2:
            import asyncio
            await asyncio.sleep(2 ** attempt)

    raise RuntimeError(
        f"Claude API failed after 3 attempts: {last_error}"
    )


async def call_claude_json(
    user_prompt: str,
    system_prompt: str = "",
    **kwargs,
) -> dict[str, Any]:
    """Call Claude and parse the response as JSON.

    Same parameters as call_claude, but returns parsed dict.
    """
    raw = await call_claude(
        user_prompt=user_prompt,
        system_prompt=system_prompt,
        json_output=True,
        **kwargs,
    )
    return parse_json_response(raw)
