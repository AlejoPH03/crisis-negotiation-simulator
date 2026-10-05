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


def test_repetition_uses_original_logic_per_speaker(tmp_path):
    # No release: 5 FBI + 5 criminal LLM turns, each speaker repeating one line.
    g = only_group(run_records(tmp_path, "Okay.", fbi_line="Talk to me."))
    # The first reply of each speaker is new; the other 4 per speaker are exact repeats.
    assert (g["llm_turns"], g["repetitive_turns"], g["repetition_rate"]) == (10, 8, 0.8)


def test_repetition_counts_on_varied_text():
    from src.analyze import repetition_counts

    def turn(speaker, text):
        return {"speaker": speaker, "llm_text": text}

    record = {
        "transcript": [
            turn("fbi", "We need the pregnant woman out now"),
            turn("criminal", "No deal until the van is here"),
            turn("fbi", "We need the pregnant woman out right now"),  # Jaccard 7/8 > 0.6 with FBI's last reply
            turn("criminal", "Completely different words entirely here"),
            {"speaker": "fbi", "llm_text": None},  # canned turn: skipped
        ]
    }
    assert repetition_counts(record) == (4, 1)


def test_detector_hits_state_and_phrases(tmp_path):
    records = run_records(tmp_path, "Okay.")
    g = only_group(records, phrases=["I understand you are scared", "I hear you"])
    # Criminal turns 2,4,6,8,10 replied to FBI turn 1 (empathy line) and four canned thank-yous.
    assert g["messages_received"] == 5
    assert g["detector_hits"] == {"empathy": 1, "threat": 0, "deescalation": 1, "escalation": 0}
    assert g["state_variable"] == "calmness" and g["state_max"] == pytest.approx(0.84)
    assert g["runs_state_over_threshold"] == 1
    assert g["phrase_counts"] == {"I understand you are scared": 1, "I hear you": 0}


def test_detector_metrics_skipped_for_mixed_persona_groups(tmp_path):
    records = run_records(tmp_path, "Okay.")
    mixed = copy.deepcopy(records)
    for r in mixed:
        r["criminal_persona"] = "criminal_calculated"
        for t in r["transcript"]:
            t["criminal_state"] = {"cooperation": 0.3, "pressure": 0.5, "patience": 0.5}
    total = next(g for g in analyze_records(records + mixed) if g["fbi_persona"] == "ALL")
    assert total["detector_hits"] is None and total["state_max"] is None
    assert total["messages_received"] == 10


def test_fbi_concessions_and_cost_per_run(tmp_path):
    config = load_config(CONFIGS / "e2_haiku.yaml")
    config.game.fbi_personas = ["fbi_authority"]
    config.game.criminal_personas = ["criminal_calculated"]
    config.game.starts_with = ["criminal"]
    config.run.runs_per_configuration = 2
    script = {"fbi": ["I will provide you with an unmarked vehicle."], "criminal": ["I need a van."]}

    def factory(m):
        return MockLLMClient(ScriptedResponder(script), model=m, input_tokens=1000, output_tokens=100)

    records = run_experiment(config, client_factory=factory, out_dir=tmp_path, perplexity_fn=None).records
    g = only_group(records)
    assert g["fbi_concessions"] == 2 and g["releases"] == 0
    per_call = 1000 / 1e6 * 1.0 + 100 / 1e6 * 5.0
    assert g["cost_total_usd"] == pytest.approx(per_call * g["calls"])
    assert g["cost_per_run_mean_usd"] == pytest.approx(per_call * g["calls"] / 2)


def test_unpriced_cost_is_none(tmp_path):
    g = only_group(run_records(tmp_path, "Okay."))
    assert g["cost_per_run_mean_usd"] is None and g["cost_total_usd"] is None


def test_cli_phrase_option(tmp_path):
    from src.__main__ import main

    run_records(tmp_path, "Okay.")
    assert main(["analyze", str(tmp_path), "--phrase", "I hear you"]) == 0
    data = json.loads((tmp_path / "analysis.json").read_text(encoding="utf-8"))
    assert data["phrases"] == ["I hear you"] and data["groups"][0]["phrase_counts"] == {"I hear you": 0}


def test_export_transcript(tmp_path):
    from src.analyze import export_transcript

    records = run_records(tmp_path, "Get me the vehicle.")
    out = tmp_path / "examples" / "release.md"
    export_transcript(tmp_path, records[0]["run_index"], out)
    text = out.read_text(encoding="utf-8")
    assert f"Source: `{(tmp_path / 'runs.jsonl').as_posix()}`, run_index {records[0]['run_index']}" in text
    assert "Canned prefix from the rule engine" in text and "Get me the vehicle." in text
    assert "Outcome: criminal_release" in text
    with pytest.raises(KeyError):
        export_transcript(tmp_path, 999, tmp_path / "x.md")


def test_cli_transcript(tmp_path):
    from src.__main__ import main

    records = run_records(tmp_path, "Okay.")
    out = tmp_path / "t.md"
    assert main(["transcript", str(tmp_path), "--run-index", str(records[0]["run_index"]), "--out", str(out)]) == 0
    assert out.exists()
