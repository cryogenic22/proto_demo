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

    def create_batch(self, poll_interval: int = 10, timeout: int = 3600) -> OpenAIBatchManager | None:
        """Create an OpenAI Batch Manager for async batch processing.

        Returns None if provider is not OpenAI or batch mode is disabled.
        Only works with OpenAI (not Azure or Anthropic).
        """
        if self.config.llm_provider != "openai" or not self.config.openai_batch_mode:
            return None
        # Need the sync client for file operations
        from openai import AsyncOpenAI
        client = AsyncOpenAI(
            api_key=self.config.openai_api_key or None,
            timeout=120.0,
        )
        return OpenAIBatchManager(client, poll_interval=poll_interval, timeout=timeout)


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
# OpenAI Batch Manager (async file-based batch processing)
# ---------------------------------------------------------------------------

class OpenAIBatchManager:
    """Manages OpenAI Batch API for async processing.

    Collects requests, submits as a JSONL batch file, polls for completion,
    and returns results. 50% cheaper than real-time API calls.

    Usage:
        batch = OpenAIBatchManager(client)
        batch.add("req-1", model, messages, max_tokens)
        batch.add("req-2", model, messages, max_tokens)
        results = await batch.submit_and_wait()
        # results = {"req-1": "response text", "req-2": "response text"}
    """

    def __init__(self, client, poll_interval: int = 10, timeout: int = 3600):
        self._client = client
        self._requests: list[dict] = []
        self._poll_interval = poll_interval
        self._timeout = timeout

    def add(self, custom_id: str, model: str, messages: list[dict],
            max_tokens: int = 4096, temperature: float = 0.0):
        """Add a request to the batch."""
        self._requests.append({
            "custom_id": custom_id,
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
        })

    @property
    def size(self) -> int:
        return len(self._requests)

    async def submit_and_wait(self) -> dict[str, str]:
        """Submit batch and wait for results.

        Returns dict mapping custom_id → response text.
        """
        if not self._requests:
            return {}

        import io
        import json as _json
        import time

        # Create JSONL content
        jsonl = "\n".join(_json.dumps(r) for r in self._requests)
        jsonl_bytes = jsonl.encode("utf-8")

        logger.info(f"Submitting OpenAI batch with {len(self._requests)} requests")

        # Upload the batch file
        file_obj = await self._client.files.create(
            file=io.BytesIO(jsonl_bytes),
            purpose="batch",
        )

        # Create the batch
        batch = await self._client.batches.create(
            input_file_id=file_obj.id,
            endpoint="/v1/chat/completions",
            completion_window="24h",
        )

        logger.info(f"Batch created: {batch.id}, status: {batch.status}")

        # Poll for completion
        start_time = time.time()
        while True:
            batch = await self._client.batches.retrieve(batch.id)

            if batch.status == "completed":
                break
            elif batch.status in ("failed", "expired", "cancelled"):
                raise RuntimeError(f"Batch {batch.id} {batch.status}: {batch.errors}")

            elapsed = time.time() - start_time
            if elapsed > self._timeout:
                raise RuntimeError(f"Batch {batch.id} timed out after {self._timeout}s")

            logger.debug(f"Batch {batch.id}: {batch.status}, {elapsed:.0f}s elapsed")
            await asyncio.sleep(self._poll_interval)

        # Download results
        if not batch.output_file_id:
            raise RuntimeError(f"Batch completed but no output file")

        output_file = await self._client.files.content(batch.output_file_id)
        output_text = output_file.text

        # Parse results
        results: dict[str, str] = {}
        for line in output_text.strip().split("\n"):
            if not line.strip():
                continue
            entry = _json.loads(line)
            custom_id = entry.get("custom_id", "")
            response = entry.get("response", {})
            body = response.get("body", {})
            choices = body.get("choices", [])
            if choices:
                text = choices[0].get("message", {}).get("content", "")
                results[custom_id] = text

        logger.info(f"Batch complete: {len(results)}/{len(self._requests)} results")
        self._requests.clear()
        return results


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
