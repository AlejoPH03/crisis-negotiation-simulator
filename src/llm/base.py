"""Shared LLM client interface (FR-1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class GenerationSettings:
    """Sampling settings passed on every call (from config)."""

    temperature: float
    max_tokens: int


@dataclass
class LLMResponse:
    """One completed LLM call."""

    text: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_s: float | None = None
    stop_reason: str | None = None
    attempts: int = 1
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


class LLMError(Exception):
    """An LLM call failed. Never turned into dialogue (NF-2)."""

    def __init__(
        self,
        message: str,
        *,
        retryable: bool,
        retry_after_s: float | None = None,
        attempts: int = 1,
    ):
        super().__init__(message)
        self.retryable = retryable
        self.retry_after_s = retry_after_s
        self.attempts = attempts


class LLMClient(Protocol):
    """Backend-neutral chat interface.

    `system` is the system prompt. `messages` holds only user/assistant turns.
    """

    model: str

    def generate(
        self,
        system: str,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        *,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse: ...
