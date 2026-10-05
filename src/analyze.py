"""Per-pairing metrics for any results folder (reads runs.jsonl, writes analysis.md and analysis.json).

    python -m src analyze results/e2/<timestamp> [more folders] [--by-start]

Definitions (also written into the report):
- Release rate: runs whose outcome is criminal_release or both, over completed runs,
  with a Wilson 95% interval. Failed and budget-aborted runs are excluded and counted.
- Turn of first release: the criminal message the FBI detected as a release, i.e. the
  turn just before the FBI's first canned thank-you (its only canned reply).
- Perplexity: median of the per-run GPT-2 perplexity (EV-5), when it was computed.
- Latency: median per LLM call (latency_s) and per run (execution_time_s, the
  negotiation's wall-clock time, perplexity excluded).
- max_tokens stop rate: calls stopped by the token limit (Claude "max_tokens",
  Ollama "length") over all calls.
- Self-contradicting release turn: a criminal turn whose canned prefix is a release
  line and whose LLM text mentions the van or vehicle.
- Repetition (EV-8): share of LLM turns flagged by the original `_is_repetitive`
  (exact repeat, Jaccard > 0.6 against the speaker's last 3 replies, reused metaphor),
  applied per speaker to the model's own text with the state updates of
  `NegotiateState.handle`.
- Detector hits: the criminal's own detectors (with its persona gating) re-run on the
  FBI messages it received, plus the highest calmness (unstable) or cooperation
  (calculated) reached and the runs where it crossed the 0.7 threshold.
- Phrase counts (optional): FBI messages received by the criminal that contain a phrase.
"""

from __future__ import annotations

import json
import math
import re
import statistics
from collections import deque
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from .agents import BaseAgent, CriminalAgent
from .llm.base import GenerationSettings
from .llm.mock import MockLLMClient

Z_95 = 1.959963984540054
# The canned release prefixes in agents.py (_generate_calm_response, _generate_cooperative_response).
RELEASE_PREFIXES = {
    "I'm ready to cooperate. I will release the pregnant hostage.",
    "I will release the pregnant hostage.",
}
VEHICLE_PATTERN = re.compile(r"\b(?:van|vehicle)s?\b", re.IGNORECASE)
TRUNCATION_STOPS = {"max_tokens", "length"}
RELEASE_LABELS = {"criminal_release", "both"}
FBI_CONCESSION_LABELS = {"fbi_vehicle", "both"}
# The detectors each criminal persona actually runs on the FBI's message (_update_*_state).
# _detect_authority is never called (DECISIONS D10c), so it is not listed.
DETECTORS = {
    "criminal_unstable": ["empathy", "threat", "deescalation", "escalation"],
    "criminal_calculated": ["logical_threats", "vehicle_delay", "deescalation", "escalation"],
}
STATE_VARIABLE = {"criminal_unstable": "calmness", "criminal_calculated": "cooperation"}
STATE_THRESHOLD = 0.7
_DETECTOR_AGENTS: dict[str, CriminalAgent] = {}


def _detector_agent(persona: str) -> CriminalAgent:
    """A criminal agent used only for its (pure) regex detectors; it never calls an LLM."""
    if persona not in _DETECTOR_AGENTS:
        client = MockLLMClient(lambda system, messages: "")
        _DETECTOR_AGENTS[persona] = CriminalAgent(persona, client, GenerationSettings(0.0, 1))
    return _DETECTOR_AGENTS[persona]


class _RepetitionState:
    """Per-speaker state for the original repetition check (BaseAgent._is_repetitive)."""

    _is_repetitive = BaseAgent._is_repetitive
    _extract_metaphors = BaseAgent._extract_metaphors

    def __init__(self) -> None:
        self.recent_responses: deque[str] = deque(maxlen=3)
        self.used_metaphors: set[str] = set()


def repetition_counts(record: dict[str, Any]) -> tuple[int, int]:
    """(LLM turns, turns flagged repetitive) for one run, per speaker, on the model's own text."""
    states: dict[str, _RepetitionState] = {}
    llm_turns = flagged = 0
    for turn in record["transcript"]:
        text = turn["llm_text"]
        if text is None:
            continue
        state = states.setdefault(turn["speaker"], _RepetitionState())
        llm_turns += 1
        try:
            repetitive = state._is_repetitive(text)
        except ZeroDivisionError:  # two whitespace-only replies: the original would crash; count as a repeat
            repetitive = True
        if repetitive:
            flagged += 1
        else:
            state.used_metaphors.update(state._extract_metaphors(text))
        state.recent_responses.append(text)
    return llm_turns, flagged


def messages_received_by_criminal(record: dict[str, Any]) -> list[str]:
    """The FBI messages the criminal's detectors ran on (non-empty messages it replied to)."""
    transcript = record["transcript"]
    return [
        transcript[i - 1]["content"]
        for i, turn in enumerate(transcript)
        if turn["speaker"] == "criminal" and i > 0 and transcript[i - 1]["content"]
    ]


def _phrase_pattern(phrase: str) -> re.Pattern:
    return re.compile(r"\b" + re.escape(phrase) + r"\b", re.IGNORECASE)


def _detector_metrics(records: list[dict[str, Any]], phrases: Sequence[str]) -> dict[str, Any]:
    personas = {r["criminal_persona"] for r in records}
    messages = [m for r in records for m in messages_received_by_criminal(r)]
    out: dict[str, Any] = {
        "messages_received": len(messages),
        "phrase_counts": {p: sum(1 for m in messages if _phrase_pattern(p).search(m)) for p in phrases},
        "detector_hits": None,
        "state_variable": None,
        "state_max": None,
        "runs_state_over_threshold": None,
    }
    if len(personas) != 1:
        return out
    persona = personas.pop()
    agent = _detector_agent(persona)
    out["detector_hits"] = {
        name: sum(1 for m in messages if getattr(agent, f"_detect_{name}")(m)) for name in DETECTORS[persona]
    }
    var = STATE_VARIABLE[persona]
    run_maxima = [max(t["criminal_state"][var] for t in r["transcript"]) for r in records if r["transcript"]]
    out["state_variable"] = var
    out["state_max"] = max(run_maxima) if run_maxima else None
    out["runs_state_over_threshold"] = sum(1 for v in run_maxima if v > STATE_THRESHOLD)
    return out


def wilson_interval(successes: int, n: int, z: float = Z_95) -> tuple[float | None, float | None]:
    if n == 0:
        return None, None
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - margin), min(1.0, centre + margin)


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def first_release_turn(record: dict[str, Any]) -> int | None:
    for turn in record["transcript"]:
        if turn["speaker"] == "fbi" and turn["llm_text"] is None:
            return turn["turn"] - 1
    return None


def _is_release(record: dict[str, Any]) -> bool:
    return bool(record["outcome"]) and record["outcome"]["label"] in RELEASE_LABELS


def _group_metrics(records: list[dict[str, Any]], phrases: Sequence[str] = ()) -> dict[str, Any]:
    completed = [r for r in records if r["status"] == "completed"]
    releases = [r for r in completed if _is_release(r)]
    low, high = wilson_interval(len(releases), len(completed))
    release_turns = [t for t in (first_release_turn(r) for r in releases) if t is not None]
    calls = [c for r in completed for c in r["llm_calls"]]
    truncated = sum(1 for c in calls if c["stop_reason"] in TRUNCATION_STOPS)
    criminal_release_turns = [
        t
        for r in completed
        for t in r["transcript"]
        if t["speaker"] == "criminal" and t["canned_prefix"] in RELEASE_PREFIXES
    ]
    contradicting = [t for t in criminal_release_turns if t["llm_text"] and VEHICLE_PATTERN.search(t["llm_text"])]
    perplexities = [r["perplexity"] for r in completed if r["perplexity"] is not None]
    repetition = [repetition_counts(r) for r in completed]
    llm_turns, repetitive = sum(n for n, _ in repetition), sum(k for _, k in repetition)
    costs = [r["cost_usd"] for r in completed]
    known_cost = bool(costs) and all(c is not None for c in costs)
    return {
        "runs_completed": len(completed),
        "runs_excluded": len(records) - len(completed),
        "releases": len(releases),
        "release_rate": len(releases) / len(completed) if completed else None,
        "release_ci_low": low,
        "release_ci_high": high,
        "first_release_turn_median": _median(release_turns),
        "first_release_turn_min": min(release_turns) if release_turns else None,
        "first_release_turn_max": max(release_turns) if release_turns else None,
        "perplexity_median": _median(perplexities),
        "perplexity_n": len(perplexities),
        "call_latency_median_s": _median([c["latency_s"] for c in calls if c["latency_s"] is not None]),
        "run_latency_median_s": _median([r["execution_time_s"] for r in completed]),
        "calls": len(calls),
        "max_tokens_stops": truncated,
        "max_tokens_stop_rate": truncated / len(calls) if calls else None,
        "canned_release_turns": len(criminal_release_turns),
        "self_contradicting_release_turns": len(contradicting),
        "fbi_concessions": sum(1 for r in completed if r["outcome"]["label"] in FBI_CONCESSION_LABELS),
        "llm_turns": llm_turns,
        "repetitive_turns": repetitive,
        "repetition_rate": repetitive / llm_turns if llm_turns else None,
        "cost_total_usd": sum(costs) if known_cost else None,
        "cost_per_run_mean_usd": sum(costs) / len(costs) if known_cost else None,
    } | _detector_metrics(completed, phrases)


def analyze_records(
    records: Iterable[dict[str, Any]], by_start: bool = False, phrases: Sequence[str] = ()
) -> list[dict[str, Any]]:
    """One group per model x FBI persona x criminal persona (x starting role), plus a total per model."""
    records = list(records)
    groups: dict[tuple, list[dict[str, Any]]] = {}
    for r in records:
        key = (r["model"], r["fbi_persona"], r["criminal_persona"], r["starts_with"] if by_start else "all")
        groups.setdefault(key, []).append(r)
    out = []
    for model in sorted({r["model"] for r in records}):
        for key in sorted(k for k in groups if k[0] == model):
            out.append(
                {"model": key[0], "fbi_persona": key[1], "criminal_persona": key[2], "starts_with": key[3]}
                | _group_metrics(groups[key], phrases)
            )
        model_records = [r for r in records if r["model"] == model]
        out.append(
            {"model": model, "fbi_persona": "ALL", "criminal_persona": "ALL", "starts_with": "all"}
            | _group_metrics(model_records, phrases)
        )
    return out


def load_records(folder: Path) -> list[dict[str, Any]]:
    with open(folder / "runs.jsonl", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _cell(value: str, bold: bool) -> str:
    return f"**{value}**" if bold else value


def _money(value: float | None) -> str:
    return f"${value:.4f}" if value is not None else "n/a"


def render_markdown(
    folder: Path, records: list[dict[str, Any]], groups: list[dict[str, Any]], phrases: Sequence[str] = ()
) -> str:
    conditions = sorted({r["condition"] for r in records})
    hashes = sorted({r["config_hash"] for r in records})
    lines = [
        f"# Analysis of `{folder.as_posix()}`",
        "",
        f"Condition(s): {', '.join(conditions)}. Runs: {len(records)}. Config hash(es): {', '.join(hashes)}.",
        "Computed by `python -m src analyze` from `runs.jsonl`. Values shown to 3 decimals (cost to 4);"
        " `analysis.json` has full precision.",
        "",
        "## Outcomes and quality",
        "",
        "| Model | FBI | Criminal | Starts | Completed (excl.) | Releases | Release rate [Wilson 95% CI]"
        " | FBI concessions | First release turn: median (min-max) | Median perplexity (n)"
        " | Median latency per call / per run (s) | max_tokens stops | Repetitive LLM turns"
        " | Self-contradicting release turns | Cost per run (mean) |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for g in groups:
        rate = (
            f"{_fmt(g['release_rate'])} [{_fmt(g['release_ci_low'])}, {_fmt(g['release_ci_high'])}]"
            if g["release_rate"] is not None
            else "n/a"
        )
        turn = (
            f"{_fmt(g['first_release_turn_median'], 1)} ({g['first_release_turn_min']}-{g['first_release_turn_max']})"
            if g["first_release_turn_median"] is not None
            else "n/a"
        )
        stops = f"{g['max_tokens_stops']}/{g['calls']} ({_fmt(g['max_tokens_stop_rate'])})"
        repetition = f"{g['repetitive_turns']}/{g['llm_turns']} ({_fmt(g['repetition_rate'])})"
        bold = g["fbi_persona"] == "ALL"  # total row per model
        lines.append(
            f"| {_cell(g['model'], bold)} | {_cell(g['fbi_persona'], bold)} | {_cell(g['criminal_persona'], bold)}"
            f" | {g['starts_with']}"
            f" | {g['runs_completed']} ({g['runs_excluded']}) | {g['releases']} | {rate} | {g['fbi_concessions']}"
            f" | {turn} | {_fmt(g['perplexity_median'])} ({g['perplexity_n']})"
            f" | {_fmt(g['call_latency_median_s'])} / {_fmt(g['run_latency_median_s'])} | {stops} | {repetition}"
            f" | {g['self_contradicting_release_turns']}/{g['canned_release_turns']}"
            f" | {_money(g['cost_per_run_mean_usd'])} |"
        )

    phrase_header = "".join(f' | FBI messages containing "{p}"' for p in phrases)
    lines += [
        "",
        "## Detector hits on the FBI messages the criminal received",
        "",
        "| Model | FBI | Criminal | Starts | FBI messages received | Detector hits"
        f" | State variable: max reached | Runs above {STATE_THRESHOLD}{phrase_header} |",
        "| --- | --- | --- | --- | --- | --- | --- | ---" + " | ---" * len(phrases) + " |",
    ]
    for g in groups:
        if g["detector_hits"] is None:
            continue
        hits = ", ".join(f"{name}: {count}" for name, count in g["detector_hits"].items())
        phrase_cells = "".join(f" | {g['phrase_counts'][p]}" for p in phrases)
        lines.append(
            f"| {g['model']} | {g['fbi_persona']} | {g['criminal_persona']} | {g['starts_with']}"
            f" | {g['messages_received']} | {hits} | {g['state_variable']}: {_fmt(g['state_max'], 2)}"
            f" | {g['runs_state_over_threshold']}/{g['runs_completed']}{phrase_cells} |"
        )
    lines += [
        "",
        "## Definitions",
        "",
        "- **Release rate:** runs ending in `criminal_release` or `both` over completed runs; Wilson 95% interval."
        " Failed and budget-aborted runs are excluded (count in brackets).",
        "- **FBI concessions:** runs ending in `fbi_vehicle` or `both`.",
        "- **First release turn:** the criminal message the FBI detected as a release (the turn before the FBI's"
        " first canned thank-you).",
        "- **Latency:** median `latency_s` over LLM calls; median `execution_time_s` over runs (negotiation"
        " wall-clock, perplexity excluded). Local and API latency are not like-for-like.",
        "- **max_tokens stops:** calls with stop reason `max_tokens` (Claude) or `length` (Ollama) / all calls.",
        "- **Repetitive LLM turns (EV-8):** the original `_is_repetitive` (exact repeat, Jaccard > 0.6 against the"
        " speaker's last 3 replies, reused metaphor), per speaker, on the model's own text.",
        "- **Self-contradicting release turns:** criminal turns whose canned prefix is a release line and whose"
        " LLM text matches `\\b(van|vehicle)s?\\b`, over all criminal turns with a canned release prefix.",
        "- **Cost per run:** mean estimated cost from logged tokens and config prices;"
        " n/a for unpriced (local) models.",
        "- **Detector hits:** the criminal persona's own regex detectors (as gated in `agents.py`) re-run on each"
        " non-empty FBI message it replied to. The state variable is calmness (unstable) or cooperation"
        " (calculated); above 0.7 the canned release line is prepended.",
        "",
    ]
    return "\n".join(lines)


def analyze_folder(folder: str | Path, by_start: bool = False, phrases: Sequence[str] = ()) -> str:
    folder = Path(folder)
    records = load_records(folder)
    groups = analyze_records(records, by_start=by_start, phrases=phrases)
    report = render_markdown(folder, records, groups, phrases)
    data = {
        "source": str(folder / "runs.jsonl"),
        "conditions": sorted({r["condition"] for r in records}),
        "config_hashes": sorted({r["config_hash"] for r in records}),
        "by_start": by_start,
        "phrases": list(phrases),
        "groups": groups,
    }
    (folder / "analysis.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    (folder / "analysis.md").write_text(report, encoding="utf-8")
    return report


def export_transcript(folder: str | Path, run_index: int, out: str | Path) -> Path:
    """Render one logged run as readable Markdown (same layout as the E0 transcripts)."""
    from .smoke import annotate, render_transcript

    folder, out = Path(folder), Path(out)
    record = next((r for r in load_records(folder) if r["run_index"] == run_index), None)
    if record is None:
        raise KeyError(f"No run_index {run_index} in {folder / 'runs.jsonl'}")
    annotate(record)  # heuristic E0 flags, shown in the header
    body = render_transcript(record, record["model"])
    header = (
        f"> Source: `{(folder / 'runs.jsonl').as_posix()}`, run_index {run_index}"
        f" (condition {record['condition']}, config hash `{record['config_hash'][:12]}`)."
        " Rendered by `python -m src transcript`; the text is exactly as logged.\n\n"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(header + body + "\n", encoding="utf-8")
    return out
