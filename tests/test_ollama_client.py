import httpx
import ollama
import pytest

from src.llm.base import LLMError
from src.llm.ollama_client import OllamaClient
from src.llm.retry import RetryPolicy

OPTS = {"top_k": 50, "top_p": 0.95, "frequency_penalty": 0.6, "presence_penalty": 0.6}
NO_WAIT = RetryPolicy(max_retries=2, base_delay_s=0, max_delay_s=0, jitter=False)


def make_client(**kw):
    return OllamaClient("gemma3:4b", backend_options=OPTS, retry=NO_WAIT, sleep=lambda s: None, **kw)


def test_exact_v0_call_and_usage(monkeypatch):
    calls = []

    def fake_chat(**kwargs):
        calls.append(kwargs)
        return {"message": {"content": "hello"}, "prompt_eval_count": 12, "eval_count": 3, "done_reason": "stop"}

    monkeypatch.setattr(ollama, "chat", fake_chat)
    resp = make_client().generate("SYS", [{"role": "user", "content": "hi"}], temperature=0.6, max_tokens=150)

    assert calls == [
        {
            "model": "gemma3:4b",
            "messages": [{"role": "system", "content": "SYS"}, {"role": "user", "content": "hi"}],
            "options": {
                "temperature": 0.6,
                "max_tokens": 150,
                "top_k": 50,
                "top_p": 0.95,
                "frequency_penalty": 0.6,
                "presence_penalty": 0.6,
            },
        }
    ]
    assert (resp.text, resp.input_tokens, resp.output_tokens, resp.attempts) == ("hello", 12, 3, 1)
    assert resp.latency_s is not None


def test_opening_turn_unchanged_for_ollama(monkeypatch):
    calls = []
    monkeypatch.setattr(ollama, "chat", lambda **kw: calls.append(kw) or {"message": {"content": "x"}})
    make_client().generate("SYS", [], temperature=0.6, max_tokens=150)
    assert calls[0]["messages"] == [{"role": "system", "content": "SYS"}]


def test_missing_content_raises_instead_of_placeholder(monkeypatch):
    monkeypatch.setattr(ollama, "chat", lambda **kw: {"done": True})
    with pytest.raises(LLMError) as exc:
        make_client().generate("SYS", [], temperature=0.6, max_tokens=150)
    assert not exc.value.retryable


@pytest.mark.parametrize(
    "error,retryable",
    [
        (ConnectionError("Failed to connect to Ollama"), True),
        (httpx.ReadTimeout("timeout"), True),
        (ollama.ResponseError("server error", 500), True),
        (ollama.ResponseError("busy", 503), True),
        (ollama.ResponseError("rate", 429), True),
        (ollama.ResponseError("model 'gemma3:4b' not found", 404), False),
        (ollama.ResponseError("bad request", 400), False),
    ],
)
def test_error_mapping_and_retries(monkeypatch, error, retryable):
    calls = []

    def boom(**kw):
        calls.append(1)
        raise error

    monkeypatch.setattr(ollama, "chat", boom)
    with pytest.raises(LLMError) as exc:
        make_client().generate("SYS", [], temperature=0.6, max_tokens=150)
    assert exc.value.retryable is retryable
    expected_calls = NO_WAIT.max_retries + 1 if retryable else 1
    assert len(calls) == expected_calls
    assert exc.value.attempts == expected_calls


def test_retry_then_success(monkeypatch):
    outcomes = [ollama.ResponseError("busy", 503), {"message": {"content": "ok"}}]

    def flaky(**kw):
        item = outcomes.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(ollama, "chat", flaky)
    resp = make_client().generate("SYS", [], temperature=0.6, max_tokens=150)
    assert (resp.text, resp.attempts) == ("ok", 2)
