"""Mock LLM clients for tests and --dry-run. No network."""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

from .base import LLMError, LLMResponse

# Persona markers taken from the persona system prompts in agents.py.
PERSONA_MARKERS = {
    "Agent Sarah Chen": "fbi_empathy",
    "Agent Michael Stone": "fbi_authority",
    "Alex Jones": "criminal_unstable",
    "James Petrusky": "criminal_calculated",
}


def persona_from_system(system: str) -> str:
    for marker, persona in PERSONA_MARKERS.items():
        if marker in system:
            return persona
    raise ValueError("Could not identify persona from system prompt")


class MockLLMClient:
    """Returns text from `responder(system, messages)` and records every request."""

    def __init__(
        self,
        responder: Callable[[str, list[dict[str, str]]], str],
        model: str = "mock-model",
        input_tokens: int = 100,
        output_tokens: int = 50,
        stop_reason: str = "end_turn",
    ):
        self.model = model
        self.responder = responder
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.stop_reason = stop_reason
        self.requests: list[dict[str, Any]] = []

    def generate(
        self,
        system: str,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        *,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        self.requests.append(
            {
                "system": system,
                "messages": copy.deepcopy(messages),
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        return LLMResponse(
            text=self.responder(system, messages),
            model=self.model,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            latency_s=0.0,
            stop_reason=self.stop_reason,
        )


class FailingLLMClient:
    """Always raises, as if retries were exhausted."""

    def __init__(self, retryable: bool = True, attempts: int = 6, model: str = "failing-model"):
        self.model = model
        self.retryable = retryable
        self.attempts = attempts
        self.calls = 0

    def generate(self, system, messages, tools=None, *, temperature, max_tokens) -> LLMResponse:
        self.calls += 1
        raise LLMError("simulated server error 529", retryable=self.retryable, attempts=self.attempts)


DRY_RUN_LINES = {
    "fbi_empathy": [
        "I understand you are scared. Let's work together to make sure everyone is safe.",
        "I hear your frustration. We need to verify a few things first before we can provide anything.",
        "I care about your safety and I want to help you get through this.",
    ],
    "fbi_authority": [
        "You must release the pregnant hostage immediately. Our tactical team is ready.",
        "This is your last chance. You're facing life in prison.",
        "Hostage-taking carries maximum penalties. Comply now.",
    ],
    "criminal_unstable": [
        "I want the car! Nobody comes near this door.",
        "Stop talking and get me that vehicle.",
        "I don't trust you. I need that unmarked vehicle.",
    ],
    "criminal_calculated": [
        "I need an unmarked vehicle out back. Then we talk about the hostages.",
        "Delays only raise the stakes. The vehicle, please.",
        "You know my terms. A vehicle, no tracking.",
    ],
}


def dry_run_client(model: str) -> MockLLMClient:
    """Deterministic canned replies, cycling per persona, for --dry-run."""
    counters: dict[str, int] = {}

    def respond(system: str, messages: list[dict[str, str]]) -> str:
        persona = persona_from_system(system)
        i = counters.get(persona, 0)
        counters[persona] = i + 1
        lines = DRY_RUN_LINES[persona]
        return f"[dry-run] {lines[i % len(lines)]}"

    return MockLLMClient(respond, model=f"{model} (dry-run)")
