"""Key proof that the refactor did not change behaviour (E1).

Runs the frozen v0-university code (tests/v0_reference, verified against the
tag) and the refactored code on the same scripted LLM replies and the same
seed, for all 8 configurations, and requires identical transcripts, outcomes
and LLM requests.
"""

from __future__ import annotations

import importlib
import itertools
import random
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import ollama
import pytest
from scripted import HAND_SCRIPTS, FakeOllamaChat, ScriptedResponder, random_script

from src.llm.mock import MockLLMClient
from src.llm.ollama_client import OllamaClient
from src.simulate import GenerationSettings, run_negotiation

V0_DIR = Path(__file__).parent / "v0_reference"
V0_MODULES = ["agents", "states", "utils", "simulate", "metrics"]

FBI = ["fbi_empathy", "fbi_authority"]
CRIMINAL = ["criminal_unstable", "criminal_calculated"]
STARTS = ["fbi", "criminal"]
CONFIGS = list(itertools.product(FBI, CRIMINAL, STARTS))

V0_OPTIONS = {
    "temperature": 0.6,
    "max_tokens": 150,
    "top_k": 50,
    "top_p": 0.95,
    "frequency_penalty": 0.6,
    "presence_penalty": 0.6,
}
BACKEND_OPTIONS = {k: v for k, v in V0_OPTIONS.items() if k not in ("temperature", "max_tokens")}
GEN = GenerationSettings(temperature=0.6, max_tokens=150)
MAX_ROUNDS = 10


@pytest.fixture(scope="module")
def v0():
    saved = {name: sys.modules.pop(name) for name in V0_MODULES if name in sys.modules}
    stub_metrics = types.ModuleType("metrics")
    stub_metrics.compute_perplexity = lambda text: 0.0  # never load GPT-2 in tests
    sys.modules["metrics"] = stub_metrics
    sys.path.insert(0, str(V0_DIR))
    try:
        yield SimpleNamespace(simulate=importlib.import_module("simulate"))
    finally:
        sys.path.remove(str(V0_DIR))
        for name in V0_MODULES:
            sys.modules.pop(name, None)
        sys.modules.update(saved)


def run_v0(v0, monkeypatch, script, config, seed):
    fake = FakeOllamaChat(ScriptedResponder(script))
    monkeypatch.setattr(ollama, "chat", fake)
    random.seed(seed)
    result = v0.simulate.run_negotiation(*config, max_rounds=MAX_ROUNDS)
    return result, fake.calls


def run_refactored_mock(script, config, seed):
    client = MockLLMClient(ScriptedResponder(script))
    result = run_negotiation(*config, max_rounds=MAX_ROUNDS, llm=client, rng=random.Random(seed), generation=GEN)
    requests = [[{"role": "system", "content": r["system"]}, *r["messages"]] for r in client.requests]
    return result, requests, client.requests


def run_refactored_ollama(monkeypatch, script, config, seed):
    fake = FakeOllamaChat(ScriptedResponder(script))
    monkeypatch.setattr(ollama, "chat", fake)
    client = OllamaClient("gemma3:4b", backend_options=BACKEND_OPTIONS)
    result = run_negotiation(*config, max_rounds=MAX_ROUNDS, llm=client, rng=random.Random(seed), generation=GEN)
    return result, fake.calls


def outcome(result):
    return {k: result[k] for k in ("history", "transcript", "criminal_conceded", "fbi_conceded", "rounds_taken")}


SCRIPTS = [(f"hand:{name}", script) for name, script in HAND_SCRIPTS.items()] + [
    (f"random:{i}", random_script(i)) for i in range(25)
]


@pytest.mark.parametrize("config", CONFIGS, ids=["-".join(c) for c in CONFIGS])
@pytest.mark.parametrize("script_id,script", SCRIPTS, ids=[s[0] for s in SCRIPTS])
@pytest.mark.parametrize("seed", [0, 7])
def test_mock_client_matches_v0(v0, monkeypatch, config, script_id, script, seed):
    expected, v0_calls = run_v0(v0, monkeypatch, script, config, seed)
    actual, requests, raw_requests = run_refactored_mock(script, config, seed)

    assert outcome(actual) == outcome(expected)
    assert requests == [call["messages"] for call in v0_calls]
    for call, raw in zip(v0_calls, raw_requests, strict=True):
        assert call["model"] == "gemma3:4b"
        assert call["options"]["temperature"] == raw["temperature"]
        assert call["options"]["max_tokens"] == raw["max_tokens"]


@pytest.mark.parametrize("config", CONFIGS, ids=["-".join(c) for c in CONFIGS])
@pytest.mark.parametrize("script_id,script", SCRIPTS[:10], ids=[s[0] for s in SCRIPTS[:10]])
def test_ollama_client_sends_identical_calls(v0, monkeypatch, config, script_id, script):
    expected, v0_calls = run_v0(v0, monkeypatch, script, config, seed=3)
    actual, new_calls = run_refactored_ollama(monkeypatch, script, config, seed=3)

    assert outcome(actual) == outcome(expected)
    assert new_calls == v0_calls  # same model, messages and options dict
    assert all(call["options"] == V0_OPTIONS for call in new_calls)


def test_canned_lines_depend_on_seed(v0, monkeypatch):
    """Guard against a vacuous equivalence: seeds must change some canned lines."""
    script = HAND_SCRIPTS["no_concession"]
    config = ("fbi_authority", "criminal_unstable", "criminal")
    transcripts = {tuple(m["content"] for m in run_refactored_mock(script, config, s)[0]["history"]) for s in range(10)}
    assert len(transcripts) > 1


EXPECTED_HAND_OUTCOMES = [
    # (script, config, criminal_conceded, fbi_conceded)
    ("release", ("fbi_empathy", "criminal_unstable", "fbi"), 1, 0),
    ("vehicle", ("fbi_authority", "criminal_calculated", "criminal"), 0, 1),
    ("no_concession", ("fbi_authority", "criminal_calculated", "fbi"), 0, 0),
    ("fbi_self_agreement", ("fbi_empathy", "criminal_calculated", "fbi"), 0, 0),
    ("criminal_self_agreement", ("fbi_empathy", "criminal_calculated", "criminal"), 0, 0),
]


@pytest.mark.parametrize("name,config,crim,fbi", EXPECTED_HAND_OUTCOMES)
def test_hand_scripts_exercise_their_branch(name, config, crim, fbi):
    """The hand-written scripts really reach the branches they are meant to cover."""
    result, _, _ = run_refactored_mock(HAND_SCRIPTS[name], config, seed=0)
    assert (result["criminal_conceded"], result["fbi_conceded"]) == (crim, fbi)
    if name == "no_concession":
        assert result["rounds_taken"] == MAX_ROUNDS
    if name.endswith("self_agreement"):
        assert result["rounds_taken"] < MAX_ROUNDS  # ended early with no concession
