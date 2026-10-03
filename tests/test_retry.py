import random

import pytest

from src.llm.base import LLMError
from src.llm.retry import RetryPolicy, call_with_retries


def flaky(outcomes):
    items = list(outcomes)
    calls = []

    def fn():
        calls.append(1)
        item = items.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    return fn, calls


def test_exponential_delays_capped():
    policy = RetryPolicy(max_retries=6, base_delay_s=2, max_delay_s=10, jitter=False)
    rng = random.Random(0)
    assert [policy.delay(n, None, rng) for n in range(1, 6)] == [2, 4, 8, 10, 10]


def test_jitter_stays_within_half_to_full_delay():
    policy = RetryPolicy(base_delay_s=4, max_delay_s=60, jitter=True)
    rng = random.Random(1)
    for n in range(1, 5):
        d = policy.delay(n, None, rng)
        full = 4 * 2 ** (n - 1)
        assert full / 2 <= d <= full


def test_retry_after_is_a_floor():
    policy = RetryPolicy(base_delay_s=1, max_delay_s=60, jitter=False)
    assert policy.delay(1, 20, random.Random()) == 20
    assert policy.delay(1, 500, random.Random()) == 60  # capped


def test_succeeds_after_retryable_errors():
    sleeps = []
    fn, calls = flaky([LLMError("529", retryable=True), LLMError("500", retryable=True), "done"])
    result, attempts = call_with_retries(fn, RetryPolicy(max_retries=5, base_delay_s=1, jitter=False), sleeps.append)
    assert (result, attempts, len(calls), sleeps) == ("done", 3, 3, [1, 2])


def test_gives_up_after_max_retries():
    fn, calls = flaky([LLMError("429", retryable=True)] * 10)
    with pytest.raises(LLMError) as exc:
        call_with_retries(fn, RetryPolicy(max_retries=3, base_delay_s=0, jitter=False), lambda s: None)
    assert len(calls) == 4 and exc.value.attempts == 4


def test_non_retryable_not_retried():
    fn, calls = flaky([LLMError("401", retryable=False), "never"])
    with pytest.raises(LLMError):
        call_with_retries(fn, RetryPolicy(max_retries=3), lambda s: None)
    assert len(calls) == 1


def test_other_exceptions_propagate_untouched():
    fn, calls = flaky([KeyError("bug")])
    with pytest.raises(KeyError):
        call_with_retries(fn, RetryPolicy(max_retries=3), lambda s: None)
    assert len(calls) == 1
