"""Results analysis script (per-pairing metrics for any results folder)."""

import copy
import json
import random
from pathlib import Path

import pytest
from scripted import ScriptedResponder

from src.agents import CriminalAgent
from src.analyze import RELEASE_PREFIXES, analyze_folder, analyze_records, wilson_interval
from src.config import load_config
from src.llm.mock import FailingLLMClient, MockLLMClient
from src.runner import run_experiment
from src.simulate import GenerationSettings

CONFIGS = Path(__file__).parent.parent / "configs"
EMPATHY = "I understand you are scared. Let's work together to make sure everyone is safe."


@pytest.mark.parametrize(
    "k,n,low,high",
    [(0, 10, 0.0, 0.2775), (5, 10, 0.2366, 0.7634), (10, 10, 0.7225, 1.0), (3, 80, 0.0128, 0.1045)],
)
def test_wilson_interval_known_values(k, n, low, high):
    lo, hi = wilson_interval(k, n)
    assert lo == pytest.approx(low, abs=1e-4) and hi == pytest.approx(high, abs=1e-4)


def test_wilson_interval_empty():
    assert wilson_interval(0, 0) == (None, None)


def test_release_prefixes_match_agent_canned_lines():
    gen = GenerationSettings(0.6, 150)
    unstable = CriminalAgent("criminal_unstable", MockLLMClient(lambda s, m: ""), gen, random.Random(0))
    calculated = CriminalAgent("criminal_calculated", MockLLMClient(lambda s, m: ""), gen, random.Random(0))
    assert {unstable._generate_calm_response(""), calculated._generate_cooperative_response("")} == RELEASE_PREFIXES


def run_records(tmp_path, criminal_line, *, fbi_line=EMPATHY, stop_reason="end_turn", runs=1, factory=None):
    config = load_config(CONFIGS / "e1_gemma.yaml")
    config.game.fbi_personas = ["fbi_empathy"]
    config.game.criminal_personas = ["criminal_unstable"]
    config.game.starts_with = ["fbi"]
    config.run.runs_per_configuration = runs
    script = {"fbi": [fbi_line], "criminal": [criminal_line]}
    factory = factory or (lambda m: MockLLMClient(ScriptedResponder(script), model=m, stop_reason=stop_reason))
    return run_experiment(config, client_factory=factory, out_dir=tmp_path, perplexity_fn=lambda t: 42.0).records


def only_group(records, **kw):
    groups = [g for g in analyze_records(records, **kw) if g["fbi_persona"] != "ALL"]
    assert len(groups) == 1
    return groups[0]


def test_release_turn_and_self_contradictions(tmp_path):
    records = run_records(tmp_path, "Get me the vehicle now. And the van keys.")
    g = only_group(records)
    # Turn 1 FBI empathy calms the unstable criminal; turn 2 carries the canned release line.
    assert (g["runs_completed"], g["releases"], g["release_rate"]) == (1, 1, 1.0)
    assert g["first_release_turn_median"] == 2
    # Every criminal turn (2, 4, 6, 8, 10) has the calm release prefix plus vehicle text.
    assert g["canned_release_turns"] == 5
    assert g["self_contradicting_release_turns"] == 5
    assert g["perplexity_median"] == 42.0 and g["perplexity_n"] == 1


def test_release_without_vehicle_text_is_not_contradiction(tmp_path):
    g = only_group(run_records(tmp_path, "Okay. Fine."))
    assert g["canned_release_turns"] == 5 and g["self_contradicting_release_turns"] == 0


def test_vehicle_word_matching_is_whole_word(tmp_path):
    g = only_group(run_records(tmp_path, "Vanessa is here. The vehicular route is clear."))
    assert g["self_contradicting_release_turns"] == 0


def test_no_release(tmp_path):
    g = only_group(run_records(tmp_path, "Get me the car.", fbi_line="Talk to me."))
    assert (g["releases"], g["release_rate"], g["first_release_turn_median"]) == (0, 0.0, None)
    assert g["release_ci_high"] == pytest.approx(0.7935, abs=1e-4)  # Wilson upper bound for 0/1


@pytest.mark.parametrize("stop", ["max_tokens", "length"])
def test_max_tokens_stop_rate_counts_claude_and_ollama(tmp_path, stop):
    g = only_group(run_records(tmp_path, "Okay.", stop_reason=stop))
    assert g["calls"] > 0 and g["max_tokens_stops"] == g["calls"] and g["max_tokens_stop_rate"] == 1.0


def test_latency_medians(tmp_path):
    records = run_records(tmp_path, "Okay.", fbi_line="Talk to me.", runs=3)
    for i, rec in enumerate(records):
        rec["execution_time_s"] = [10.0, 30.0, 20.0][i]
        for j, call in enumerate(rec["llm_calls"]):
            call["latency_s"] = float(j)  # 0..9 in each run
    g = only_group(records)
    assert g["run_latency_median_s"] == 20.0
    assert g["call_latency_median_s"] == 4.5


def test_failed_runs_excluded_and_counted(tmp_path):
    good = run_records(tmp_path / "a", "Okay.")
    failed = run_records(tmp_path / "b", "Okay.", factory=lambda m: FailingLLMClient(model=m))
    g = only_group(good + failed)
    assert (g["runs_completed"], g["runs_excluded"]) == (1, 1)


def test_by_start_and_totals(tmp_path):
    records = run_records(tmp_path, "Okay.")
    other = copy.deepcopy(records)
    for r in other:
        r["starts_with"] = "criminal"
        r["outcome"] = {"criminal_conceded": 0, "fbi_conceded": 0, "label": "none"}
    groups = analyze_records(records + other, by_start=True)
    keyed = {(g["fbi_persona"], g["starts_with"]): g for g in groups}
    assert keyed[("fbi_empathy", "fbi")]["releases"] == 1
    assert keyed[("fbi_empathy", "criminal")]["releases"] == 0
    total = next(g for g in analyze_records(records + other) if g["fbi_persona"] == "ALL")
    assert (total["runs_completed"], total["releases"], total["release_rate"]) == (2, 1, 0.5)


def test_analyze_folder_writes_outputs(tmp_path):
    run_records(tmp_path, "Get me the vehicle.")
    report = analyze_folder(tmp_path)
    data = json.loads((tmp_path / "analysis.json").read_text(encoding="utf-8"))
    assert data["source"] == str(tmp_path / "runs.jsonl")
    assert data["config_hashes"] and data["groups"][0]["releases"] == 1
    md = (tmp_path / "analysis.md").read_text(encoding="utf-8")
    assert md == report and "Wilson" in md and "fbi_empathy" in md
    assert (tmp_path / "runs.jsonl").exists()  # source left untouched


def test_cli_analyze(tmp_path, capsys):
    from src.__main__ import main

    run_records(tmp_path, "Okay.")
    assert main(["analyze", str(tmp_path)]) == 0
    assert "fbi_empathy" in capsys.readouterr().out
    assert main(["analyze", str(tmp_path / "missing")]) == 1
