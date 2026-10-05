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
"""

from __future__ import annotations

import json
import math
import re
import statistics
from collections.abc import Iterable
from pathlib import Path
from typing import Any

Z_95 = 1.959963984540054
# The canned release prefixes in agents.py (_generate_calm_response, _generate_cooperative_response).
RELEASE_PREFIXES = {
    "I'm ready to cooperate. I will release the pregnant hostage.",
    "I will release the pregnant hostage.",
}
VEHICLE_PATTERN = re.compile(r"\b(?:van|vehicle)s?\b", re.IGNORECASE)
TRUNCATION_STOPS = {"max_tokens", "length"}
RELEASE_LABELS = {"criminal_release", "both"}


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


def _group_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
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
    }


def analyze_records(records: Iterable[dict[str, Any]], by_start: bool = False) -> list[dict[str, Any]]:
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
                | _group_metrics(groups[key])
            )
        model_records = [r for r in records if r["model"] == model]
        out.append(
            {"model": model, "fbi_persona": "ALL", "criminal_persona": "ALL", "starts_with": "all"}
            | _group_metrics(model_records)
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


def render_markdown(folder: Path, records: list[dict[str, Any]], groups: list[dict[str, Any]]) -> str:
    conditions = sorted({r["condition"] for r in records})
    hashes = sorted({r["config_hash"] for r in records})
    lines = [
        f"# Analysis of `{folder.as_posix()}`",
        "",
        f"Condition(s): {', '.join(conditions)}. Runs: {len(records)}. Config hash(es): {', '.join(hashes)}.",
        "Computed by `python -m src analyze` from `runs.jsonl`. Values shown to 3 decimals;"
        " `analysis.json` has full precision.",
        "",
        "| Model | FBI | Criminal | Starts | Completed (excl.) | Releases | Release rate [Wilson 95% CI]"
        " | First release turn: median (min-max) | Median perplexity (n) | Median latency per call / per run (s)"
        " | max_tokens stops | Self-contradicting release turns |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
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
        bold = g["fbi_persona"] == "ALL"  # total row per model
        lines.append(
            f"| {_cell(g['model'], bold)} | {_cell(g['fbi_persona'], bold)} | {_cell(g['criminal_persona'], bold)}"
            f" | {g['starts_with']}"
            f" | {g['runs_completed']} ({g['runs_excluded']}) | {g['releases']} | {rate} | {turn}"
            f" | {_fmt(g['perplexity_median'])} ({g['perplexity_n']})"
            f" | {_fmt(g['call_latency_median_s'])} / {_fmt(g['run_latency_median_s'])} | {stops}"
            f" | {g['self_contradicting_release_turns']}/{g['canned_release_turns']} |"
        )
    lines += [
        "",
        "## Definitions",
        "",
        "- **Release rate:** runs ending in `criminal_release` or `both` over completed runs; Wilson 95% interval."
        " Failed and budget-aborted runs are excluded (count in brackets).",
        "- **First release turn:** the criminal message the FBI detected as a release (the turn before the FBI's"
        " first canned thank-you).",
        "- **Latency:** median `latency_s` over LLM calls; median `execution_time_s` over runs (negotiation"
        " wall-clock, perplexity excluded).",
        "- **max_tokens stops:** calls with stop reason `max_tokens` (Claude) or `length` (Ollama) / all calls.",
        "- **Self-contradicting release turns:** criminal turns whose canned prefix is a release line and whose"
        " LLM text matches `\\b(van|vehicle)s?\\b`, over all criminal turns with a canned release prefix.",
        "",
    ]
    return "\n".join(lines)


def analyze_folder(folder: str | Path, by_start: bool = False) -> str:
    folder = Path(folder)
    records = load_records(folder)
    groups = analyze_records(records, by_start=by_start)
    report = render_markdown(folder, records, groups)
    data = {
        "source": str(folder / "runs.jsonl"),
        "conditions": sorted({r["condition"] for r in records}),
        "config_hashes": sorted({r["config_hash"] for r in records}),
        "by_start": by_start,
        "groups": groups,
    }
    (folder / "analysis.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    (folder / "analysis.md").write_text(report, encoding="utf-8")
    return report
