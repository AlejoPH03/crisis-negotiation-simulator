from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from src.llm.base import LLMError
from src.llm.claude_client import ClaudeClient, to_claude_messages
from src.llm.retry import RetryPolicy

OPENING = "(The phone line connects. You speak first.)"
NO_WAIT = RetryPolicy(max_retries=3, base_delay_s=1, max_delay_s=30, jitter=False)
REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def api_response(text="Hello.", stop_reason="end_turn", blocks=None):
    content = blocks if blocks is not None else [SimpleNamespace(type="text", text=text)]
    return SimpleNamespace(
        content=content, stop_reason=stop_reason, usage=SimpleNamespace(input_tokens=420, output_tokens=37)
    )


class FakeMessages:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        item = self.outcomes.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def make_client(outcomes, sleeps=None):
    fake = SimpleNamespace(messages=FakeMessages(outcomes))
    sleeps = sleeps if sleeps is not None else []
    client = ClaudeClient("claude-haiku-4-5", OPENING, retry=NO_WAIT, client=fake, sleep=sleeps.append)
    return client, fake.messages


def status_error(cls, status, headers=None):
    response = httpx2.Response(status, headers=headers or {}, request=REQUEST)
    return cls("error", response=response, body=None)


def test_system_goes_in_system_param():
    client, api = make_client([api_response("Hi.")])
    resp = client.generate("PERSONA", [{"role": "user", "content": "Talk."}], temperature=0.6, max_tokens=300)
    call = api.calls[0]
    assert call == {
        "model": "claude-haiku-4-5",
        "system": "PERSONA",
        "messages": [{"role": "user", "content": "Talk."}],
        "temperature": 0.6,
        "max_tokens": 300,
    }
    assert all(m["role"] != "system" for m in call["messages"])
    assert (resp.text, resp.input_tokens, resp.output_tokens, resp.stop_reason) == ("Hi.", 420, 37, "end_turn")
    assert resp.model == "claude-haiku-4-5" and resp.attempts == 1


def test_opening_turn_added_when_agent_speaks_first():
    client, api = make_client([api_response()])
    client.generate("PERSONA", [], temperature=0.6, max_tokens=300)
    assert api.calls[0]["messages"] == [{"role": "user", "content": OPENING}]


def test_message_conversion_rules():
    assert to_claude_messages([{"role": "assistant", "content": "a"}], OPENING) == [
        {"role": "user", "content": OPENING},
        {"role": "assistant", "content": "a"},
    ]
    merged = to_claude_messages(
        [{"role": "user", "content": "a"}, {"role": "user", "content": "b"}, {"role": "assistant", "content": "c"}],
        OPENING,
    )
    assert merged == [{"role": "user", "content": "a\n\nb"}, {"role": "assistant", "content": "c"}]
    with pytest.raises(ValueError):
        to_claude_messages([{"role": "system", "content": "x"}], OPENING)


def test_text_blocks_joined_and_refusal_recorded():
    blocks = [SimpleNamespace(type="text", text="I can't "), SimpleNamespace(type="text", text="continue.")]
    client, _ = make_client([api_response(blocks=blocks, stop_reason="refusal")])
    resp = client.generate("P", [], temperature=0.6, max_tokens=300)
    assert (resp.text, resp.stop_reason) == ("I can't continue.", "refusal")


def test_empty_content_is_empty_text_not_error():
    client, _ = make_client([api_response(blocks=[], stop_reason="max_tokens")])
    resp = client.generate("P", [], temperature=0.6, max_tokens=300)
    assert (resp.text, resp.stop_reason) == ("", "max_tokens")


@pytest.mark.parametrize(
    "error",
    [
        status_error(anthropic.RateLimitError, 429),
        status_error(anthropic.InternalServerError, 500),
        status_error(anthropic.OverloadedError, 529),
        status_error(anthropic.ServiceUnavailableError, 503),
        anthropic.APIConnectionError(request=REQUEST),
        anthropic.APITimeoutError(request=REQUEST),
    ],
    ids=lambda e: type(e).__name__,
)
def test_retryable_errors_back_off_then_succeed(error):
    sleeps = []
    client, api = make_client([error, error, api_response("ok")], sleeps)
    resp = client.generate("P", [], temperature=0.6, max_tokens=300)
    assert resp.text == "ok" and resp.attempts == 3
    assert sleeps == [1, 2]  # exponential backoff, jitter off
    assert len(api.calls) == 3


def test_retry_after_header_honoured():
    sleeps = []
    err = status_error(anthropic.RateLimitError, 429, headers={"retry-after": "7"})
    client, _ = make_client([err, api_response("ok")], sleeps)
    client.generate("P", [], temperature=0.6, max_tokens=300)
    assert sleeps == [7.0]


def test_retries_exhausted_raise():
    err = status_error(anthropic.OverloadedError, 529)
    client, api = make_client([err] * 4)
    with pytest.raises(LLMError) as exc:
        client.generate("P", [], temperature=0.6, max_tokens=300)
    assert exc.value.retryable and exc.value.attempts == 4 and len(api.calls) == 4


@pytest.mark.parametrize(
    "cls,status",
    [
        (anthropic.BadRequestError, 400),
        (anthropic.AuthenticationError, 401),
        (anthropic.PermissionDeniedError, 403),
        (anthropic.NotFoundError, 404),
    ],
)
def test_client_errors_not_retried(cls, status):
    client, api = make_client([status_error(cls, status)])
    with pytest.raises(LLMError) as exc:
        client.generate("P", [], temperature=0.6, max_tokens=300)
    assert not exc.value.retryable and len(api.calls) == 1


def test_api_key_only_from_env_and_never_shown(monkeypatch):
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        ClaudeClient("claude-haiku-4-5", OPENING)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-secret")
    client = ClaudeClient("claude-haiku-4-5", OPENING)
    assert "sk-ant-test-secret" not in repr(client)
    assert client._client.max_retries == 0  # retry.py is the only retry policy
