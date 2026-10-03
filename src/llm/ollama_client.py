"""Ollama backend. Reproduces the v0 `ollama.chat` call exactly."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx
import ollama

from .base import LLMError, LLMResponse
from .retry import RetryPolicy, call_with_retries

# Only these become LLMError (D23). Anything else is a bug and raises unchanged.
# ollama raises the built-in ConnectionError when it cannot reach the server.
WRAPPED_ERRORS = (ollama.ResponseError, ollama.RequestError, ConnectionError, httpx.HTTPError)


def _to_llm_error(e: Exception) -> LLMError:
    if isinstance(e, ollama.ResponseError):
        status = getattr(e, "status_code", None) or 0
        retryable = status == 429 or status >= 500
        return LLMError(f"Ollama error {status}: {e}", retryable=retryable)
    if isinstance(e, (ConnectionError, httpx.TransportError)):
        return LLMError(f"Ollama connection error: {e}", retryable=True)
    return LLMError(f"Ollama call failed: {type(e).__name__}: {e}", retryable=False)


def _get(obj: Any, key: str) -> Any:
    """Read a field from a dict or an ollama response object."""
    try:
        return obj[key]
    except (KeyError, TypeError):
        return getattr(obj, key, None)


class OllamaClient:
    def __init__(
        self,
        model: str,
        backend_options: dict[str, Any] | None = None,
        retry: RetryPolicy | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.model = model
        self.backend_options = dict(backend_options or {})
        self.retry = retry or RetryPolicy()
        self._sleep = sleep

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
        # Same message list and options dict as v0 BaseAgent.get_response.
        # Note: Ollama's token limit option is `num_predict`; `max_tokens` is
        # passed through unchanged for fidelity (see docs/DECISIONS.md).
        chat_messages = [{"role": "system", "content": system}, *messages]
        options = {"temperature": temperature, "max_tokens": max_tokens, **self.backend_options}

        def call() -> tuple[Any, float]:
            start = time.perf_counter()
            try:
                response = ollama.chat(model=self.model, messages=chat_messages, options=options)
            except WRAPPED_ERRORS as e:
                raise _to_llm_error(e) from e
            return response, time.perf_counter() - start

        (response, latency), attempts = call_with_retries(call, self.retry, self._sleep)
        message = _get(response, "message")
        content = _get(message, "content") if message is not None else None
        if content is None:
            raise LLMError("Ollama response had no message content", retryable=False, attempts=attempts)
        return LLMResponse(
            text=content,
            model=self.model,
            input_tokens=_get(response, "prompt_eval_count"),
            output_tokens=_get(response, "eval_count"),
            latency_s=latency,
            stop_reason=_get(response, "done_reason"),
            attempts=attempts,
        )
