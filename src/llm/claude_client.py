"""Claude backend via the Anthropic Python SDK."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Any

import anthropic

from .base import LLMError, LLMResponse
from .retry import RetryPolicy, call_with_retries

API_KEY_ENV = "ANTHROPIC_API_KEY"
RETRYABLE_STATUS = {408, 409, 429}


def _retry_after(e: anthropic.APIStatusError) -> float | None:
    try:
        value = e.response.headers.get("retry-after")
        return float(value) if value is not None else None
    except (AttributeError, TypeError, ValueError):
        return None


def _to_llm_error(e: Exception) -> LLMError:
    if isinstance(e, anthropic.APIStatusError):
        status = e.status_code
        retryable = status in RETRYABLE_STATUS or status >= 500
        return LLMError(
            f"Anthropic API error {status} ({type(e).__name__}): {e.message}",
            retryable=retryable,
            retry_after_s=_retry_after(e) if retryable else None,
        )
    if isinstance(e, anthropic.APIConnectionError):  # includes APITimeoutError
        return LLMError(f"Anthropic connection error ({type(e).__name__})", retryable=True)
    return LLMError(f"Anthropic call failed: {type(e).__name__}: {e}", retryable=False)


def to_claude_messages(messages: list[dict[str, str]], opening_user_message: str) -> list[dict[str, str]]:
    """Convert agent messages to a valid Messages API list.

    - The API needs a user turn first. When an agent speaks first (no prior
      message) or the list starts with an assistant turn, a neutral opening
      user turn is prepended. Claude only; Ollama is unchanged.
    - Consecutive turns with the same role are merged.
    """
    converted: list[dict[str, str]] = []
    for msg in messages:
        role = msg["role"]
        if role not in ("user", "assistant"):
            raise ValueError(f"Unexpected role in messages: {role!r} (system goes in `system`)")
        if converted and converted[-1]["role"] == role:
            converted[-1] = {"role": role, "content": converted[-1]["content"] + "\n\n" + msg["content"]}
        else:
            converted.append({"role": role, "content": msg["content"]})
    if not converted or converted[0]["role"] != "user":
        converted.insert(0, {"role": "user", "content": opening_user_message})
    return converted


class ClaudeClient:
    def __init__(
        self,
        model: str,
        opening_user_message: str,
        retry: RetryPolicy | None = None,
        client: Any | None = None,
        sleep: Callable[[float], None] = time.sleep,
        timeout_s: float = 120.0,
    ):
        self.model = model
        self.opening_user_message = opening_user_message
        self.retry = retry or RetryPolicy()
        self._sleep = sleep
        if client is None:
            api_key = os.environ.get(API_KEY_ENV)
            if not api_key:
                raise RuntimeError(f"{API_KEY_ENV} is not set. Put it in the environment or in .env.")
            # SDK retries off: retry.py is the single retry policy, and every attempt is logged.
            client = anthropic.Anthropic(api_key=api_key, max_retries=0, timeout=timeout_s)
        self._client = client

    def __repr__(self) -> str:
        return f"ClaudeClient(model={self.model!r})"

    def generate(
        self,
        system: str,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        *,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        if tools:
            raise NotImplementedError("Tool calling is not supported before E3.")
        api_messages = to_claude_messages(messages, self.opening_user_message)

        def call() -> tuple[Any, float]:
            start = time.perf_counter()
            try:
                response = self._client.messages.create(
                    model=self.model,
                    system=system,
                    messages=api_messages,
                    max_tokens=max_tokens,
                    # anthropic SDK 1.x removed the temperature keyword; the API still accepts the
                    # field for Haiku 4.5 / Sonnet 4.6, so it goes in the request body (FR-8, D21).
                    extra_body={"temperature": temperature},
                )
            except Exception as e:
                raise _to_llm_error(e) from e
            return response, time.perf_counter() - start

        (response, latency), attempts = call_with_retries(call, self.retry, self._sleep)
        text = "".join(block.text for block in response.content if getattr(block, "type", None) == "text")
        return LLMResponse(
            text=text,
            model=self.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            latency_s=latency,
            stop_reason=response.stop_reason,
            attempts=attempts,
        )
