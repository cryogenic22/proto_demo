"""
LLM client abstraction — supports Anthropic Claude and OpenAI GPT.

Usage:
    config = PipelineConfig(llm_provider="anthropic")  # or "openai"
    client = LLMClient(config)
    result = await client.vision_query(image_bytes, "Describe this table")
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Any

from src.models.schema import PipelineConfig

logger = logging.getLogger(__name__)


class LLMClient:
    """Unified async LLM client — auto-selects Anthropic, OpenAI, or Azure backend."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self._backend = None

    @property
    def backend(self):
        if self._backend is None:
            provider = self.config.llm_provider
            if provider == "openai":
                self._backend = _OpenAIBackend(self.config)
            elif provider == "azure":
                self._backend = _AzureOpenAIBackend(self.config)
            else:
                self._backend = _AnthropicBackend(self.config)
            logger.info(f"LLM backend: {provider}")
        return self._backend

    async def vision_query(self, image_bytes: bytes, prompt: str, *,
                           system: str = "", model: str | None = None,
                           max_tokens: int = 4096, temperature: float = 0.0) -> str:
        model = model or self.config.resolved_vision_model
        return await self.backend.vision_query(
            image_bytes, prompt, system=system, model=model,
            max_tokens=max_tokens, temperature=temperature)

    async def vision_query_multi(self, images: list[bytes], prompt: str, *,
                                 system: str = "", model: str | None = None,
                                 max_tokens: int = 8192, temperature: float = 0.0) -> str:
        model = model or self.config.resolved_vision_model
        return await self.backend.vision_query_multi(
            images, prompt, system=system, model=model,
            max_tokens=max_tokens, temperature=temperature)

    async def text_query(self, prompt: str, *, system: str = "",
                         model: str | None = None, max_tokens: int = 4096,
                         temperature: float = 0.0) -> str:
        model = model or self.config.resolved_llm_model
        return await self.backend.text_query(
            prompt, system=system, model=model,
            max_tokens=max_tokens, temperature=temperature)

    async def json_query(self, prompt: str, **kwargs) -> Any:
        raw = await self.text_query(prompt, **kwargs)
        return _extract_json(raw)

    async def vision_json_query(self, image_bytes: bytes, prompt: str, **kwargs) -> Any:
        raw = await self.vision_query(image_bytes, prompt, **kwargs)
        return _extract_json(raw)

    async def vision_json_query_multi(self, images: list[bytes], prompt: str, **kwargs) -> Any:
        raw = await self.vision_query_multi(images, prompt, **kwargs)
        return _extract_json(raw)


# ---------------------------------------------------------------------------
# Anthropic Backend
# ---------------------------------------------------------------------------

class _AnthropicBackend:
    def __init__(self, config: PipelineConfig):
        self.config = config
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.AsyncAnthropic(
                api_key=self.config.anthropic_api_key or None,
                timeout=120.0, max_retries=0,
            )
        return self._client

    async def vision_query(self, image_bytes, prompt, *, system, model, max_tokens, temperature):
        b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
        messages = [{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
            {"type": "text", "text": prompt},
        ]}]
        return await self._call(model=model, system=system, messages=messages,
                                max_tokens=max_tokens, temperature=temperature)

    async def vision_query_multi(self, images, prompt, *, system, model, max_tokens, temperature):
        content = []
        for img in images:
            b64 = base64.standard_b64encode(img).decode("utf-8")
            content.append({"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}})
        content.append({"type": "text", "text": prompt})
        messages = [{"role": "user", "content": content}]
        return await self._call(model=model, system=system, messages=messages,
                                max_tokens=max_tokens, temperature=temperature)

    async def text_query(self, prompt, *, system, model, max_tokens, temperature):
        messages = [{"role": "user", "content": prompt}]
        return await self._call(model=model, system=system, messages=messages,
                                max_tokens=max_tokens, temperature=temperature)

    async def _call(self, *, model, system, messages, max_tokens, temperature, max_retries=3):
        import anthropic
        last_error = None
        for attempt in range(max_retries):
            try:
                kwargs: dict[str, Any] = {
                    "model": model, "messages": messages,
                    "max_tokens": max_tokens, "temperature": temperature,
                }
                if system:
                    kwargs["system"] = system
                response = await self.client.messages.create(**kwargs)
                if not response.content:
                    raise ValueError("Empty response from Anthropic API")
                return response.content[0].text

            except anthropic.RateLimitError as e:
                last_error = e
                wait = 2 ** attempt + 1
                logger.warning(f"Anthropic rate limited, retry in {wait}s ({attempt+1}/{max_retries})")
                await asyncio.sleep(wait)
            except anthropic.APIStatusError as e:
                if e.status_code < 500 and e.status_code != 429:
                    logger.error(f"Anthropic API error {e.status_code}: {e.message}")
                    raise
                last_error = e
                await asyncio.sleep(2 ** attempt + 1)
            except Exception as e:
                last_error = e
                await asyncio.sleep(2 ** attempt + 1)

        raise RuntimeError(f"Anthropic: all {max_retries} retries failed: {last_error}") from last_error


# ---------------------------------------------------------------------------
# OpenAI Backend
# ---------------------------------------------------------------------------

class _OpenAIBackend:
    def __init__(self, config: PipelineConfig):
        self.config = config
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(
                api_key=self.config.openai_api_key or None,
                timeout=120.0, max_retries=0,
            )
        return self._client

    async def vision_query(self, image_bytes, prompt, *, system, model, max_tokens, temperature):
        b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
        messages = self._build_messages(system, [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"}},
            {"type": "text", "text": prompt},
        ])
        return await self._call(model=model, messages=messages,
                                max_tokens=max_tokens, temperature=temperature)

    async def vision_query_multi(self, images, prompt, *, system, model, max_tokens, temperature):
        content = []
        for img in images:
            b64 = base64.standard_b64encode(img).decode("utf-8")
            content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"}})
        content.append({"type": "text", "text": prompt})
        messages = self._build_messages(system, content)
        return await self._call(model=model, messages=messages,
                                max_tokens=max_tokens, temperature=temperature)

    async def text_query(self, prompt, *, system, model, max_tokens, temperature):
        messages = self._build_messages(system, prompt)
        return await self._call(model=model, messages=messages,
                                max_tokens=max_tokens, temperature=temperature)

    def _build_messages(self, system: str, user_content) -> list[dict]:
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": user_content})
        return msgs

    async def _call(self, *, model, messages, max_tokens, temperature, max_retries=3):
        from openai import RateLimitError, APIStatusError
        last_error = None
        for attempt in range(max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=model, messages=messages,
                    max_tokens=max_tokens, temperature=temperature,
                )
                choice = response.choices[0]
                if not choice.message.content:
                    raise ValueError("Empty response from OpenAI API")
                return choice.message.content

            except RateLimitError as e:
                last_error = e
                wait = 2 ** attempt + 1
                logger.warning(f"OpenAI rate limited, retry in {wait}s ({attempt+1}/{max_retries})")
                await asyncio.sleep(wait)
            except APIStatusError as e:
                if e.status_code < 500 and e.status_code != 429:
                    logger.error(f"OpenAI API error {e.status_code}: {e.message}")
                    raise
                last_error = e
                await asyncio.sleep(2 ** attempt + 1)
            except Exception as e:
                last_error = e
                await asyncio.sleep(2 ** attempt + 1)

        raise RuntimeError(f"OpenAI: all {max_retries} retries failed: {last_error}") from last_error


# ---------------------------------------------------------------------------
# Azure OpenAI Backend
# ---------------------------------------------------------------------------

class _AzureOpenAIBackend:
    """Azure OpenAI backend — same API as OpenAI but uses Azure endpoints."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from openai import AsyncAzureOpenAI
            self._client = AsyncAzureOpenAI(
                api_key=self.config.azure_openai_api_key or None,
                azure_endpoint=self.config.azure_openai_endpoint,
                api_version=self.config.azure_openai_api_version,
                timeout=120.0, max_retries=0,
            )
        return self._client

    async def vision_query(self, image_bytes, prompt, *, system, model, max_tokens, temperature):
        b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
        messages = self._build_messages(system, [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"}},
            {"type": "text", "text": prompt},
        ])
        return await self._call(model=model, messages=messages,
                                max_tokens=max_tokens, temperature=temperature)

    async def vision_query_multi(self, images, prompt, *, system, model, max_tokens, temperature):
        content = []
        for img in images:
            b64 = base64.standard_b64encode(img).decode("utf-8")
            content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"}})
        content.append({"type": "text", "text": prompt})
        messages = self._build_messages(system, content)
        return await self._call(model=model, messages=messages,
                                max_tokens=max_tokens, temperature=temperature)

    async def text_query(self, prompt, *, system, model, max_tokens, temperature):
        messages = self._build_messages(system, prompt)
        return await self._call(model=model, messages=messages,
                                max_tokens=max_tokens, temperature=temperature)

    def _build_messages(self, system: str, user_content) -> list[dict]:
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": user_content})
        return msgs

    async def _call(self, *, model, messages, max_tokens, temperature, max_retries=3):
        from openai import RateLimitError, APIStatusError
        # For Azure, model = deployment name
        deployment = self.config.azure_openai_deployment or model
        last_error = None
        for attempt in range(max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=deployment, messages=messages,
                    max_tokens=max_tokens, temperature=temperature,
                )
                choice = response.choices[0]
                if not choice.message.content:
                    raise ValueError("Empty response from Azure OpenAI API")
                return choice.message.content

            except RateLimitError as e:
                last_error = e
                wait = 2 ** attempt + 1
                logger.warning(f"Azure rate limited, retry in {wait}s ({attempt+1}/{max_retries})")
                await asyncio.sleep(wait)
            except APIStatusError as e:
                if e.status_code < 500 and e.status_code != 429:
                    logger.error(f"Azure API error {e.status_code}: {e.message}")
                    raise
                last_error = e
                await asyncio.sleep(2 ** attempt + 1)
            except Exception as e:
                last_error = e
                await asyncio.sleep(2 ** attempt + 1)

        raise RuntimeError(f"Azure OpenAI: all {max_retries} retries failed: {last_error}") from last_error


# ---------------------------------------------------------------------------
# JSON extraction (shared)
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> Any:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
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
    for i, ch in enumerate(text):
        if ch in ("[", "{"):
            try:
                return json.loads(text[i:])
            except json.JSONDecodeError:
                continue
    logger.warning(f"Could not extract JSON from LLM response: {text[:200]}...")
    return []
