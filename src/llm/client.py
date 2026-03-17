"""
LLM client abstraction wrapping Anthropic Claude API.

Provides vision + text calls with retry logic and structured output support.
All network/API errors are caught and retried.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Any

import anthropic

from src.models.schema import PipelineConfig

logger = logging.getLogger(__name__)


class LLMClient:
    """Async wrapper around the Anthropic API with vision support."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self._client: anthropic.AsyncAnthropic | None = None

    @property
    def client(self) -> anthropic.AsyncAnthropic:
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(
                api_key=self.config.anthropic_api_key or None,
                timeout=120.0,
                max_retries=0,  # We handle retries ourselves
            )
        return self._client

    async def vision_query(
        self,
        image_bytes: bytes,
        prompt: str,
        *,
        system: str = "",
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> str:
        """Send an image + text prompt to the vision model."""
        model = model or self.config.vision_model
        b64_image = base64.standard_b64encode(image_bytes).decode("utf-8")

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": b64_image,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ]

        response = await self._call_with_retry(
            model=model,
            system=system,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response

    async def vision_query_multi(
        self,
        images: list[bytes],
        prompt: str,
        *,
        system: str = "",
        model: str | None = None,
        max_tokens: int = 8192,
        temperature: float = 0.0,
    ) -> str:
        """Send multiple images + text prompt to the vision model."""
        model = model or self.config.vision_model

        content: list[dict[str, Any]] = []
        for img in images:
            b64 = base64.standard_b64encode(img).decode("utf-8")
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": b64,
                },
            })
        content.append({"type": "text", "text": prompt})

        messages = [{"role": "user", "content": content}]

        response = await self._call_with_retry(
            model=model,
            system=system,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response

    async def text_query(
        self,
        prompt: str,
        *,
        system: str = "",
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> str:
        """Send a text-only prompt."""
        model = model or self.config.llm_model
        messages = [{"role": "user", "content": prompt}]

        response = await self._call_with_retry(
            model=model,
            system=system,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response

    async def json_query(
        self,
        prompt: str,
        *,
        system: str = "",
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> Any:
        """Send a prompt expecting JSON response. Parses and returns dict/list."""
        raw = await self.text_query(
            prompt, system=system, model=model,
            max_tokens=max_tokens, temperature=temperature,
        )
        return self._extract_json(raw)

    async def vision_json_query(
        self,
        image_bytes: bytes,
        prompt: str,
        *,
        system: str = "",
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> Any:
        """Vision query expecting JSON response."""
        raw = await self.vision_query(
            image_bytes, prompt, system=system, model=model,
            max_tokens=max_tokens, temperature=temperature,
        )
        return self._extract_json(raw)

    async def vision_json_query_multi(
        self,
        images: list[bytes],
        prompt: str,
        *,
        system: str = "",
        model: str | None = None,
        max_tokens: int = 8192,
        temperature: float = 0.0,
    ) -> Any:
        """Multi-image vision query expecting JSON response."""
        raw = await self.vision_query_multi(
            images, prompt, system=system, model=model,
            max_tokens=max_tokens, temperature=temperature,
        )
        return self._extract_json(raw)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _call_with_retry(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict],
        max_tokens: int,
        temperature: float,
        max_retries: int = 3,
    ) -> str:
        """Call the API with exponential backoff retry.

        Catches ALL exception types — network errors, API errors,
        timeouts — so callers never see raw infrastructure failures.
        """
        last_error: Exception | None = None

        for attempt in range(max_retries):
            try:
                kwargs: dict[str, Any] = {
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                }
                if system:
                    kwargs["system"] = system

                response = await self.client.messages.create(**kwargs)

                # Guard against empty response
                if not response.content:
                    raise ValueError("Empty response from API")

                return response.content[0].text

            except anthropic.RateLimitError as e:
                last_error = e
                wait = 2 ** attempt + 1
                logger.warning(f"Rate limited, retrying in {wait}s (attempt {attempt + 1}/{max_retries})")
                await asyncio.sleep(wait)

            except anthropic.APIStatusError as e:
                # 4xx errors (except 429 rate limit) are not retryable
                if e.status_code < 500 and e.status_code != 429:
                    logger.error(f"API error {e.status_code}: {e.message}")
                    raise
                last_error = e
                wait = 2 ** attempt + 1
                logger.warning(f"API server error {e.status_code}, retrying in {wait}s (attempt {attempt + 1})")
                await asyncio.sleep(wait)

            except (
                anthropic.APIConnectionError,
                anthropic.APITimeoutError,
            ) as e:
                last_error = e
                wait = 2 ** attempt + 1
                logger.warning(f"Connection/timeout error, retrying in {wait}s (attempt {attempt + 1}): {e}")
                await asyncio.sleep(wait)

            except Exception as e:
                # Catch absolutely everything else (OSError, etc.)
                last_error = e
                wait = 2 ** attempt + 1
                logger.warning(f"Unexpected error, retrying in {wait}s (attempt {attempt + 1}): {type(e).__name__}: {e}")
                await asyncio.sleep(wait)

        # All retries exhausted
        error_msg = f"All {max_retries} retries failed. Last error: {last_error}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from last_error

    @staticmethod
    def _extract_json(text: str) -> Any:
        """Extract JSON from LLM response, handling markdown code blocks."""
        text = text.strip()

        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code block
        if "```" in text:
            parts = text.split("```")
            for part in parts[1::2]:
                content = part.strip()
                if content.startswith("json"):
                    content = content[4:].strip()
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    continue

        # Last resort: find first [ or { and parse from there
        for i, ch in enumerate(text):
            if ch in ("[", "{"):
                try:
                    return json.loads(text[i:])
                except json.JSONDecodeError:
                    continue

        # Return empty list instead of crashing
        logger.warning(f"Could not extract JSON from LLM response: {text[:200]}...")
        return []
