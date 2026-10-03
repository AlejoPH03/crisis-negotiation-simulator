"""Budget cap (NF-1)."""

import json
from pathlib import Path

import pytest
from scripted import HAND_SCRIPTS, ScriptedResponder

from src.budget import BudgetedClient, BudgetExceeded, BudgetTracker, Price
from src.config import load_config
from src.llm.mock import MockLLMClient
from src.runner import run_experiment

CONFIGS = Path(__file__).parent.parent / "configs"
PRICING = {"claude-haiku-4-5": Price(input_per_mtok=1.0, output_per_mtok=5.0)}


def test_cost_from_tokens():
    tracker = BudgetTracker(cap_usd=None, pricing=PRICING)
    assert tracker.cost("claude-haiku-4-5", 1_000_000, 0) == pytest.approx(1.0)
    assert tracker.cost("claude-haiku-4-5", 2000, 400) == pytest.approx(0.002 + 0.002)
    assert tracker.cost("gemma3:4b", 1000, 1000) is None  # local model, no price


def test_check_raises_once_cap_reached():
    tracker = BudgetTracker(cap_usd=0.01, pricing=PRICING)
    tracker.check()
    tracker.record("claude-haiku-4-5", 5000, 1000)  # 0.005 + 0.005 = 0.01
    with pytest.raises(BudgetExceeded):
        tracker.check()


def test_no_cap_never_raises():
    tracker = BudgetTracker(cap_usd=None, pricing=PRICING)
    tracker.record("claude-haiku-4-5", 10**9, 10**9)
    tracker.check()


def test_budgeted_client_checks_before_each_call():
    inner = MockLLMClient(lambda s, m: "x", model="claude-haiku-4-5", input_tokens=4000, output_tokens=200)
    tracker = BudgetTracker(cap_usd=0.01, pricing=PRICING)  # each call costs 0.005
    client = BudgetedClient(inner, tracker)
    client.generate("S", [], temperature=0.6, max_tokens=300)
    client.generate("S", [], temperature=0.6, max_tokens=300)
    with pytest.raises(BudgetExceeded):
        client.generate("S", [], temperature=0.6, max_tokens=300)
    assert len(inner.requests) == 2  # the third call never reached the backend
    assert tracker.spent_usd == pytest.approx(0.01)


def test_runner_stops_at_cap(tmp_path):
    config = load_config(CONFIGS / "e2_haiku.yaml")
    config.budget.cap_usd = 0.0525  # reached during the second run (10 calls per run)
    per_call = 0.005  # 4000 in + 200 out on Haiku prices

    def factory(model):
        return MockLLMClient(
            ScriptedResponder(HAND_SCRIPTS["no_concession"]), model=model, input_tokens=4000, output_tokens=200
        )

    result = run_experiment(config, client_factory=factory, out_dir=tmp_path, perplexity_fn=None)
    records = [json.loads(line) for line in (tmp_path / "runs.jsonl").read_text(encoding="utf-8").splitlines()]
    assert result.stopped_reason == "budget_cap"
    assert [r["status"] for r in records] == ["completed", "aborted_budget"]
    assert len(records[-1]["transcript"]) == 1  # partial run kept
    total = sum(r["cost_usd"] for r in records)
    assert config.budget.cap_usd <= total <= config.budget.cap_usd + per_call + 1e-9
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary["stopped_reason"] == "budget_cap"
    assert summary["cost_usd"] == pytest.approx(total)
    assert len(records) < 80


def read_records(path):
    return [json.loads(line) for line in (path / "runs.jsonl").read_text(encoding="utf-8").splitlines()]


def test_priced_model_with_no_calls_costs_zero_not_unknown(tmp_path):
    """All runs failed before any call: cost is $0, not 'no prices for this model'."""
    from src.llm.mock import FailingLLMClient

    config = load_config(CONFIGS / "e2_haiku.yaml")
    result = run_experiment(
        config,
        client_factory=lambda m: FailingLLMClient(retryable=False, attempts=1, model=m),
        out_dir=tmp_path,
        perplexity_fn=None,
    )
    records = read_records(tmp_path)
    assert result.stopped_reason == "max_consecutive_failures"
    assert all(r["status"] == "failed" and r["cost_usd"] == 0.0 for r in records)
    assert result.summary["cost_usd"] == 0.0


def test_unpriced_model_cost_stays_unknown(tmp_path):
    config = load_config(CONFIGS / "e1_gemma.yaml")
    config.run.runs_per_configuration = 1
    factory = lambda m: MockLLMClient(ScriptedResponder(HAND_SCRIPTS["no_concession"]), model=m)  # noqa: E731
    result = run_experiment(config, client_factory=factory, out_dir=tmp_path, perplexity_fn=None)
    assert all(r["cost_usd"] is None for r in result.records)
    assert result.summary["cost_usd"] is None


def test_e2_cost_through_real_sdk_uses_configured_model_price(tmp_path):
    """Real SDK request/response path (mock transport, no network): the API's dated model id
    must not break the price lookup."""
    from test_claude_client import RecordingTransport, real_sdk_client

    config = load_config(CONFIGS / "e2_haiku.yaml")
    config.run.runs_per_configuration = 1
    transport = RecordingTransport(api_model="claude-haiku-4-5-20251001")
    result = run_experiment(
        config, client_factory=lambda m: real_sdk_client(transport, m), out_dir=tmp_path, perplexity_fn=None
    )
    records = read_records(tmp_path)
    assert all(r["status"] == "completed" for r in records)
    assert all(body["temperature"] == 0.6 and body["max_tokens"] == 300 for body in transport.bodies)
    n_calls = sum(len(r["llm_calls"]) for r in records)
    expected = n_calls * (512 / 1e6 * 1.0 + 9 / 1e6 * 5.0)
    assert result.summary["cost_usd"] == pytest.approx(expected)
    assert all(r["cost_usd"] > 0 for r in records)
