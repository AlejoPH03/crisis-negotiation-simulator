"""Exponential backoff for retryable LLM errors (NF-2)."""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass

from .base import LLMError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int = 5
    base_delay_s: float = 2.0
    max_delay_s: float = 60.0
    jitter: bool = True

    def delay(self, retry_number: int, retry_after_s: float | None, rng: random.Random) -> float:
        """Delay before retry `retry_number` (1-based)."""
        delay = min(self.max_delay_s, self.base_delay_s * (2 ** (retry_number - 1)))
        if self.jitter:
            delay = delay * (0.5 + rng.random() / 2)
        if retry_after_s is not None:
            delay = max(delay, min(retry_after_s, self.max_delay_s))
        return delay


# Separate RNG so retry jitter never touches the canned-line RNG (FR-11).
_jitter_rng = random.Random()


def call_with_retries[T](
    fn: Callable[[], T],
    policy: RetryPolicy,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[T, int]:
    """Run `fn`, retrying retryable LLMErrors. Returns (result, attempts).

    On final failure re-raises the LLMError with `attempts` set.
    """
    attempt = 0
    while True:
        attempt += 1
        try:
            return fn(), attempt
        except LLMError as e:
            e.attempts = attempt
            if not e.retryable or attempt > policy.max_retries:
                raise
            delay = policy.delay(attempt, e.retry_after_s, _jitter_rng)
            logger.warning(
                "LLM call failed (%s), retry %d/%d in %.1fs",
                e,
                attempt,
                policy.max_retries,
                delay,
            )
            sleep(delay)
