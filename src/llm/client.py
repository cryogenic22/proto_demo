"""
LLM client abstraction wrapping Anthropic Claude API.

Provides vision + text calls with retry logic and structured output support.
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
                api_key=self.config.anthropic_api_key or None
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
        """Call the API with exponential backoff retry."""
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
                return response.content[0].text

            except anthropic.RateLimitError as e:
                last_error = e
                wait = 2 ** attempt
                logger.warning(f"Rate limited, retrying in {wait}s (attempt {attempt + 1})")
                await asyncio.sleep(wait)

            except anthropic.APIError as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait = 2 ** attempt
                    logger.warning(f"API error: {e}, retrying in {wait}s")
                    await asyncio.sleep(wait)
                else:
                    raise

        raise last_error  # type: ignore[misc]

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
            # Find content between first ``` and last ```
            parts = text.split("```")
            for part in parts[1::2]:  # odd-indexed parts are inside code blocks
                # Strip optional language tag (e.g., "json\n")
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

        raise ValueError(f"Could not extract JSON from LLM response: {text[:200]}...")
