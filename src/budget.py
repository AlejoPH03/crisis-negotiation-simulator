"""Spend cap per experiment (NF-1). Cost is estimated from logged tokens."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .llm.base import LLMClient, LLMResponse


@dataclass(frozen=True)
class Price:
    """USD per million tokens."""

    input_per_mtok: float
    output_per_mtok: float


class BudgetExceeded(Exception):
    pass


class BudgetTracker:
    def __init__(self, cap_usd: float | None, pricing: dict[str, Price]):
        self.cap_usd = cap_usd
        self.pricing = pricing
        self.spent_usd = 0.0

    def cost(self, model: str, input_tokens: int | None, output_tokens: int | None) -> float | None:
        """Estimated cost of one call, or None for a model with no price (local)."""
        price = self.pricing.get(model)
        if price is None:
            return None
        return (input_tokens or 0) / 1e6 * price.input_per_mtok + (output_tokens or 0) / 1e6 * price.output_per_mtok

    @property
    def exhausted(self) -> bool:
        return self.cap_usd is not None and self.spent_usd >= self.cap_usd

    def check(self) -> None:
        if self.exhausted:
            raise BudgetExceeded(f"Budget cap ${self.cap_usd:.2f} reached (spent ${self.spent_usd:.4f})")

    def record(self, model: str, input_tokens: int | None, output_tokens: int | None) -> float | None:
        cost = self.cost(model, input_tokens, output_tokens)
        if cost is not None:
            self.spent_usd += cost
        return cost


class BudgetedClient:
    """Checks the cap before every call and records the cost after it."""

    def __init__(self, inner: LLMClient, tracker: BudgetTracker):
        self.inner = inner
        self.tracker = tracker
        self.model = inner.model

    def generate(
        self,
        system: str,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        *,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        self.tracker.check()
        response = self.inner.generate(system, messages, tools, temperature=temperature, max_tokens=max_tokens)
        # Dry-run clients report "<model> (dry-run)", which has no price, so dry runs cost nothing.
        self.tracker.record(response.model, response.input_tokens, response.output_tokens)
        return response
