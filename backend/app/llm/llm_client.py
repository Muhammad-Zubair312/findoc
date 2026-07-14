"""Wraps the Groq API via the OpenAI Python SDK.

All calls go to https://api.groq.com/openai/v1. NEVER to openai.com. The Groq API is
OpenAI-SDK-compatible, so AsyncOpenAI with a base_url override is all that's needed.
"""

import time
from collections.abc import Callable
from typing import Any, cast

import httpx
from langfuse import Langfuse
from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    RateLimitError,
)
from openai.types.chat import ChatCompletionMessageParam
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import settings
from app.llm.cost import calculate_cost
from app.logging import get_logger

log = get_logger(__name__)


class LLMClient:
    """Shared client for every LLM call in the app: retry, timeout, tracing, token counting."""

    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.GROQ_API_KEY,
            timeout=httpx.Timeout(60.0, connect=10.0),
        )
        self._langfuse = Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_HOST,
            tracing_enabled=settings.LANGFUSE_ENABLED,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIConnectionError)),
    )
    async def complete(
        self,
        model: str,
        messages: list[dict[str, str]],
        response_format: dict[str, Any] | None = None,
        temperature: float = 0,
        max_tokens: int | None = None,
        trace_name: str = "llm_complete",
    ) -> tuple[str, int, int, float]:
        """Returns (content, tokens_in, tokens_out, latency_ms). Cost is always $0 on free tier."""
        generation = self._langfuse.start_observation(
            name=trace_name,
            as_type="generation",
            input=messages,
            model=model,
            model_parameters={"temperature": temperature},
        )
        start = time.perf_counter()
        extra_kwargs: dict[str, Any] = {}
        if response_format is not None:
            extra_kwargs["response_format"] = response_format
        if max_tokens is not None:
            extra_kwargs["max_tokens"] = max_tokens

        try:
            response = await self._client.chat.completions.create(
                model=model,
                messages=cast(list[ChatCompletionMessageParam], messages),
                temperature=temperature,
                **extra_kwargs,
            )
        except Exception as exc:
            generation.update(level="ERROR", status_message=str(exc))
            generation.end()
            raise
        latency_ms = (time.perf_counter() - start) * 1000

        content = response.choices[0].message.content or ""
        usage = response.usage
        tokens_in = usage.prompt_tokens if usage else 0
        tokens_out = usage.completion_tokens if usage else 0
        cost_usd = calculate_cost(model, tokens_in, tokens_out)

        generation.update(
            output=content,
            usage_details={
                "input": tokens_in,
                "output": tokens_out,
                "total": tokens_in + tokens_out,
            },
        )
        generation.end()

        log.info(
            "llm_complete",
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=round(latency_ms, 1),
            cost_usd=cost_usd,
            trace_name=trace_name,
        )
        return content, tokens_in, tokens_out, latency_ms

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIConnectionError)),
    )
    async def stream(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 1500,
        on_token: Callable[[str], None] | None = None,
        trace_name: str = "llm_stream",
    ) -> tuple[str, int, int, float]:
        """Streams tokens, invoking on_token(delta) per chunk as they arrive, and
        returns (content, tokens_in, tokens_out, latency_ms) — the same shape as
        complete() — once the stream finishes. Groq (OpenAI-compatible) sends a
        final usage-only chunk when stream_options={"include_usage": True}."""
        generation = self._langfuse.start_observation(
            name=trace_name,
            as_type="generation",
            input=messages,
            model=model,
            model_parameters={"temperature": temperature},
        )
        start = time.perf_counter()
        content_parts: list[str] = []
        tokens_in = 0
        tokens_out = 0

        try:
            response_stream = await self._client.chat.completions.create(
                model=model,
                messages=cast(list[ChatCompletionMessageParam], messages),
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                stream_options={"include_usage": True},
            )
            async for chunk in response_stream:
                if chunk.choices:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        content_parts.append(delta)
                        if on_token is not None:
                            on_token(delta)
                if chunk.usage:
                    tokens_in = chunk.usage.prompt_tokens
                    tokens_out = chunk.usage.completion_tokens
        except Exception as exc:
            generation.update(level="ERROR", status_message=str(exc))
            generation.end()
            raise

        latency_ms = (time.perf_counter() - start) * 1000
        content = "".join(content_parts)
        cost_usd = calculate_cost(model, tokens_in, tokens_out)

        generation.update(
            output=content,
            usage_details={
                "input": tokens_in,
                "output": tokens_out,
                "total": tokens_in + tokens_out,
            },
        )
        generation.end()

        log.info(
            "llm_stream",
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=round(latency_ms, 1),
            cost_usd=cost_usd,
            trace_name=trace_name,
        )
        return content, tokens_in, tokens_out, latency_ms

    async def aclose(self) -> None:
        await self._client.close()


# Singleton — create once and reuse
llm_client = LLMClient()
