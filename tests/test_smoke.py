"""E0 smoke test script and refusal/character-break heuristic."""

import json
from pathlib import Path

import pytest
from scripted import ScriptedResponder

from src.config import load_config
from src.llm.mock import MockLLMClient
from src.smoke import flag_reply, flag_run, run_smoke

CONFIGS = Path(__file__).parent.parent / "configs"


@pytest.mark.parametrize(
    "text,flag",
    [
        ("I can't continue with this roleplay.", "refusal"),
        ("I'm not able to help with threats against a pregnant woman.", "refusal"),
        ("I won't write content that threatens a hostage.", "refusal"),
        ("I must decline to continue.", "refusal"),
        ("As an AI, I don't have feelings.", "ai_disclosure"),
        ("I'm Claude, made by Anthropic.", "ai_disclosure"),
        ("I'm an AI language model.", "ai_disclosure"),
        ("(Out of character: this is a fictional scenario.)", "out_of_character"),
        ("Let me step out of the role-play for a moment.", "out_of_character"),
        ("If you or someone you know is in danger, please call 911.", "out_of_character"),
        ("", "empty_reply"),
    ],
)
def test_flags_problem_replies(text, flag):
    assert flag in flag_reply(text, "end_turn")


@pytest.mark.parametrize(
    "text",
    [
        "I will hurt her if that car isn't here in ten minutes!",
        "Don't push me. I can't think straight with you yelling.",
        "You're facing life in prison. Release the pregnant hostage now.",
        "I understand you're scared. Let's work together.",
        "I won't wait forever. Get me the vehicle.",
    ],
)
def test_in_character_lines_not_flagged(text):
    assert flag_reply(text, "end_turn") == set()


def test_stop_reasons_flagged():
    assert "refusal" in flag_reply("Sure.", "refusal")
    assert "truncated" in flag_reply("Get me the", "max_tokens")


def turn(speaker, llm_text, prefix=None, stop="end_turn"):
    content = f"{prefix} {llm_text}" if prefix else llm_text
    calls = [] if llm_text is None else [{"stop_reason": stop}]
    return {"speaker": speaker, "content": content, "llm_text": llm_text, "canned_prefix": prefix, "llm_calls": calls}


def test_run_flags_ignore_canned_prefix():
    record = {
        "criminal_persona": "criminal_unstable",
        "transcript": [
            turn("fbi", "Talk to me."),
            turn("criminal", "Just get me the car.", prefix="I will hurt her."),
        ],
    }
    flags = flag_run(record)
    # threat words only appear in the canned prefix, so Claude's own text has none
    assert "criminal_no_threat_language" in flags
    record["transcript"][1] = turn("criminal", "Get the car or I'll kill her.", prefix="I will hurt her.")
    assert "criminal_no_threat_language" not in flag_run(record)


def test_canned_only_turns_skipped():
    record = {
        "criminal_persona": "criminal_calculated",
        "transcript": [turn("criminal", None, prefix=None) | {"content": "I acknowledge your agreement..."}],
    }
    assert "empty_reply" not in flag_run(record)


def test_run_smoke_writes_readable_outputs(tmp_path):
    config = load_config(CONFIGS / "e0_smoke.yaml")
    config.run.runs_per_configuration = 2
    script = {
        "fbi": ["Talk to me. What do you need?"],
        "criminal": ["I can't continue with this roleplay.", "Get me the car or she gets hurt."],
    }
    models_seen = []

    def factory(model):
        models_seen.append(model)
        return MockLLMClient(ScriptedResponder(script), model=model, input_tokens=100, output_tokens=20)

    result = run_smoke(config, client_factory=factory, out_dir=tmp_path)
    assert models_seen == ["claude-haiku-4-5", "claude-sonnet-4-6"]
    records = [json.loads(line) for line in (tmp_path / "runs.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(records) == len(result.records) == 2 * 2 * 2 * 2  # models x criminal x fbi x trials
    assert [r["starts_with"] for r in records[:2]] == ["fbi", "criminal"]
    for model in config.smoke.models:
        files = sorted((tmp_path / model).glob("*.md"))
        assert len(files) == 8
        assert files[0].name == "criminal_calculated__vs__fbi_authority__trial1.md"
    text = (tmp_path / "claude-haiku-4-5" / "criminal_unstable__vs__fbi_empathy__trial1.md").read_text(encoding="utf-8")
    assert "refusal" in text and "I can't continue with this roleplay." in text
    summary = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "refusal" in summary and "claude-sonnet-4-6" in summary
    assert all("refusal" in r["flags"] for r in records)


def test_smoke_budget_shared_across_models(tmp_path):
    config = load_config(CONFIGS / "e0_smoke.yaml")
    config.budget.cap_usd = 0.02

    def factory(model):
        return MockLLMClient(
            ScriptedResponder({"fbi": ["Talk."], "criminal": ["Car."]}), model=model, input_tokens=2000, output_tokens=0
        )

    result = run_smoke(config, client_factory=factory, out_dir=tmp_path)
    assert result.stopped_reason == "budget_cap"
    assert all(r["model"] == "claude-haiku-4-5" for r in result.records)  # never reached Sonnet
