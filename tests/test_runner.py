"""Experiment runner: JSONL schema, seeding, failed-run path (FR-11, FR-12, NF-2)."""

import json
from pathlib import Path

import pytest
from scripted import HAND_SCRIPTS, ScriptedResponder, random_script

from src.config import load_config
from src.llm.base import LLMError, LLMResponse
from src.llm.mock import FailingLLMClient, MockLLMClient
from src.runner import run_experiment

CONFIGS = Path(__file__).parent.parent / "configs"

REQUIRED_KEYS = {
    "schema_version",
    "condition",
    "config_hash",
    "config",
    "run_index",
    "trial",
    "seed",
    "fbi_persona",
    "criminal_persona",
    "starts_with",
    "backend",
    "model",
    "status",
    "error",
    "transcript",
    "llm_calls",
    "outcome",
    "rounds_taken",
    "perplexity",
    "perplexity_error",
    "execution_time_s",
    "tokens",
    "cost_usd",
    "environment",
}
TURN_KEYS = {
    "turn",
    "speaker",
    "persona",
    "content",
    "llm_text",
    "canned_prefix",
    "fbi_fsm_state",
    "criminal_fsm_state",
    "criminal_state",
    "llm_calls",
}


def cfg(name="e1_gemma.yaml", runs=2):
    config = load_config(CONFIGS / name)
    config.run.runs_per_configuration = runs
    return config


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()]


def scripted_factory(script):
    return lambda model: MockLLMClient(ScriptedResponder(script), model=model)


def test_records_schema_and_outputs(tmp_path):
    result = run_experiment(
        cfg(), client_factory=scripted_factory(random_script(1)), out_dir=tmp_path, perplexity_fn=lambda t: 12.5
    )
    records = read_jsonl(tmp_path / "runs.jsonl")
    assert len(records) == 16 == len(result.records)  # 8 configurations x 2 runs
    for rec in records:
        assert REQUIRED_KEYS <= rec.keys()
        assert rec["status"] == "completed" and rec["error"] is None
        assert rec["condition"] == "E1" and rec["model"] == "gemma3:4b"
        assert rec["rounds_taken"] == len(rec["transcript"]) <= 10
        assert rec["perplexity"] == 12.5
        assert rec["outcome"]["label"] in {"criminal_release", "fbi_vehicle", "both", "none"}
        for turn in rec["transcript"]:
            assert TURN_KEYS <= turn.keys()
            assert turn["criminal_state"]  # per-turn criminal state
        assert rec["tokens"]["input"] == sum(c["input_tokens"] for c in rec["llm_calls"])
    assert (tmp_path / "config.yaml").exists()
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary["counts"]["completed"] == 16 and summary["stopped_reason"] is None


def test_grid_order_and_seeds(tmp_path):
    config = cfg()
    run_experiment(config, client_factory=scripted_factory(random_script(2)), out_dir=tmp_path, perplexity_fn=None)
    records = read_jsonl(tmp_path / "runs.jsonl")
    order = [(r["fbi_persona"], r["criminal_persona"], r["starts_with"], r["trial"]) for r in records]
    assert order[:4] == [
        ("fbi_empathy", "criminal_unstable", "fbi", 1),
        ("fbi_empathy", "criminal_unstable", "fbi", 2),
        ("fbi_empathy", "criminal_unstable", "criminal", 1),
        ("fbi_empathy", "criminal_unstable", "criminal", 2),
    ]
    assert [r["seed"] for r in records] == [config.run.seed + i for i in range(16)]


def test_same_seed_same_transcripts(tmp_path):
    script = HAND_SCRIPTS["no_concession"]
    run_experiment(cfg(), client_factory=scripted_factory(script), out_dir=tmp_path / "a", perplexity_fn=None)
    run_experiment(cfg(), client_factory=scripted_factory(script), out_dir=tmp_path / "b", perplexity_fn=None)
    a = [r["transcript"] for r in read_jsonl(tmp_path / "a" / "runs.jsonl")]
    b = [r["transcript"] for r in read_jsonl(tmp_path / "b" / "runs.jsonl")]
    assert a == b


def test_canned_prefix_and_llm_text_recorded(tmp_path):
    factory = scripted_factory(HAND_SCRIPTS["no_concession"])
    run_experiment(cfg(runs=1), client_factory=factory, out_dir=tmp_path, perplexity_fn=None)
    rec = read_jsonl(tmp_path / "runs.jsonl")[0]
    crim_turn = next(t for t in rec["transcript"] if t["speaker"] == "criminal")
    assert crim_turn["llm_text"] == "I need a car."
    assert crim_turn["content"] == f"{crim_turn['canned_prefix']} I need a car."


def test_failed_run_is_logged_not_dialogue(tmp_path):
    result = run_experiment(cfg(), client_factory=lambda m: FailingLLMClient(), out_dir=tmp_path, perplexity_fn=None)
    records = read_jsonl(tmp_path / "runs.jsonl")
    # aborts after max_consecutive_failures (3) failed runs
    assert len(records) == 3 and result.stopped_reason == "max_consecutive_failures"
    for rec in records:
        assert rec["status"] == "failed"
        assert rec["error"]["type"] == "LLMError"
        assert rec["error"]["retryable"] is True and rec["error"]["attempts"] == 6
        assert rec["outcome"] is None and rec["perplexity"] is None
        assert "Error getting response" not in json.dumps(rec)
        assert rec["transcript"] == []
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary["counts"] == {"completed": 0, "failed": 3, "aborted_budget": 0}


class FailOnNthCall:
    """Succeeds, then fails on call n, then succeeds again."""

    def __init__(self, fail_on, model="gemma3:4b"):
        self.model = model
        self.fail_on = set(fail_on)
        self.n = 0
        self.inner = MockLLMClient(ScriptedResponder(HAND_SCRIPTS["no_concession"]), model=model)

    def generate(self, system, messages, tools=None, *, temperature, max_tokens):
        self.n += 1
        if self.n in self.fail_on:
            raise LLMError("simulated 503", retryable=True, attempts=6)
        return self.inner.generate(system, messages, temperature=temperature, max_tokens=max_tokens)


def test_partial_transcript_kept_and_runner_continues(tmp_path):
    client = FailOnNthCall(fail_on={3})
    run_experiment(cfg(runs=1), client_factory=lambda m: client, out_dir=tmp_path, perplexity_fn=None)
    records = read_jsonl(tmp_path / "runs.jsonl")
    assert len(records) == 8
    assert records[0]["status"] == "failed" and len(records[0]["transcript"]) == 2
    assert all(r["status"] == "completed" for r in records[1:])


def test_perplexity_failure_recorded_not_inf(tmp_path):
    def broken(text):
        raise RuntimeError("no model")

    run_experiment(
        cfg(runs=1), client_factory=scripted_factory(random_script(3)), out_dir=tmp_path, perplexity_fn=broken
    )
    rec = read_jsonl(tmp_path / "runs.jsonl")[0]
    assert rec["status"] == "completed" and rec["perplexity"] is None
    assert "no model" in rec["perplexity_error"]


def test_unexpected_bug_is_not_swallowed(tmp_path):
    class Buggy(MockLLMClient):
        def generate(self, *a, **k):
            raise KeyError("bug")

    with pytest.raises(KeyError):
        run_experiment(cfg(), client_factory=lambda m: Buggy(lambda s, m: ""), out_dir=tmp_path, perplexity_fn=None)


def test_usage_none_tolerated(tmp_path):
    class NoUsage(MockLLMClient):
        def generate(self, *a, **k):
            r = super().generate(*a, **k)
            return LLMResponse(text=r.text, model=r.model, input_tokens=None, output_tokens=None)

    run_experiment(
        cfg(runs=1),
        client_factory=lambda m: NoUsage(ScriptedResponder(random_script(4)), model=m),
        out_dir=tmp_path,
        perplexity_fn=None,
    )
    rec = read_jsonl(tmp_path / "runs.jsonl")[0]
    assert rec["status"] == "completed" and rec["tokens"] == {"input": 0, "output": 0}


def test_dry_run_uses_mock_and_skips_perplexity(tmp_path, monkeypatch):
    import sys

    monkeypatch.delitem(sys.modules, "src.metrics", raising=False)
    result = run_experiment(cfg(runs=1), out_dir=tmp_path, dry_run=True)
    assert all(r["status"] == "completed" and r["perplexity"] is None for r in result.records)
    assert all(r["model"].endswith("(dry-run)") and r["cost_usd"] is None for r in result.records)
    assert "src.metrics" not in sys.modules  # GPT-2 never loaded


def test_type_error_in_claude_client_crashes_run_instead_of_failed_record(tmp_path):
    """D23: a programming error in a client raises out of the experiment; no 'failed' record is written."""
    from types import SimpleNamespace

    from src.llm.claude_client import ClaudeClient
    from src.llm.retry import RetryPolicy

    class BrokenMessages:
        calls = 0

        def create(self, **kwargs):
            BrokenMessages.calls += 1
            raise TypeError("Messages.create() got an unexpected keyword argument 'temperature'")

    def factory(model):
        sdk = SimpleNamespace(messages=BrokenMessages())
        return ClaudeClient(model, "(open)", retry=RetryPolicy(max_retries=3, base_delay_s=0), client=sdk)

    with pytest.raises(TypeError, match="temperature"):
        run_experiment(cfg("e2_haiku.yaml"), client_factory=factory, out_dir=tmp_path, perplexity_fn=None)
    assert BrokenMessages.calls == 1
    assert read_jsonl(tmp_path / "runs.jsonl") == []


def test_type_error_in_ollama_client_crashes_run(tmp_path, monkeypatch):
    import ollama

    from src.llm.ollama_client import OllamaClient

    def broken_chat(**kwargs):
        raise TypeError("chat() got an unexpected keyword argument 'x'")

    monkeypatch.setattr(ollama, "chat", broken_chat)
    with pytest.raises(TypeError):
        run_experiment(cfg(), client_factory=lambda m: OllamaClient(m), out_dir=tmp_path, perplexity_fn=None)
    assert read_jsonl(tmp_path / "runs.jsonl") == []
