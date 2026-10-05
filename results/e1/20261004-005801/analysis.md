# Analysis of `results/e1/20261004-005801`

Condition(s): E1. Runs: 80. Config hash(es): 8925b8f4b3df4b3666b44025ea6ea6c2d6fccdb0db6951cea839d515983f3dc7.
Computed by `python -m src analyze` from `runs.jsonl`. Values shown to 3 decimals (cost to 4); `analysis.json` has full precision.

## Outcomes and quality

| Model | FBI | Criminal | Starts | Completed (excl.) | Releases | Release rate [Wilson 95% CI] | FBI concessions | First release turn: median (min-max) | Median perplexity (n) | Median latency per call / per run (s) | max_tokens stops | Repetitive LLM turns | Self-contradicting release turns | Cost per run (mean) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gemma3:4b | fbi_authority | criminal_calculated | all | 20 (0) | 19 | 0.950 [0.764, 0.991] | 0 | 6 (6-7) | 31.607 (20) | 29.277 / 226.640 | 0/158 (0.000) | 0/158 (0.000) | 45/48 | n/a |
| gemma3:4b | fbi_authority | criminal_unstable | all | 20 (0) | 2 | 0.100 [0.028, 0.301] | 0 | 5.5 (3-8) | 24.816 (20) | 43.844 / 416.751 | 0/194 (0.000) | 0/194 (0.000) | 0/0 | n/a |
| gemma3:4b | fbi_empathy | criminal_calculated | all | 20 (0) | 1 | 0.050 [0.009, 0.236] | 0 | 8 (8-8) | 23.924 (20) | 48.125 / 457.594 | 0/199 (0.000) | 0/199 (0.000) | 0/0 | n/a |
| gemma3:4b | fbi_empathy | criminal_unstable | all | 20 (0) | 19 | 0.950 [0.764, 0.991] | 0 | 5 (3-9) | 21.687 (20) | 37.490 / 287.587 | 0/153 (0.000) | 0/153 (0.000) | 41/56 | n/a |
| **gemma3:4b** | **ALL** | **ALL** | all | 80 (0) | 41 | 0.512 [0.405, 0.619] | 0 | 6 (3-9) | 24.813 (80) | 40.161 / 391.179 | 0/704 (0.000) | 0/704 (0.000) | 86/104 | n/a |

## Detector hits on the FBI messages the criminal received

| Model | FBI | Criminal | Starts | FBI messages received | Detector hits | State variable: max reached | Runs above 0.7 | FBI messages containing "I hear you" |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gemma3:4b | fbi_authority | criminal_calculated | all | 88 | logical_threats: 59, vehicle_delay: 0, deescalation: 0, escalation: 0 | cooperation: 0.87 | 19/20 | 0 |
| gemma3:4b | fbi_authority | criminal_unstable | all | 88 | empathy: 0, threat: 0, deescalation: 0, escalation: 0 | calmness: 0.30 | 0/20 | 0 |
| gemma3:4b | fbi_empathy | criminal_calculated | all | 90 | logical_threats: 79, vehicle_delay: 69, deescalation: 2, escalation: 0 | cooperation: 0.68 | 0/20 | 4 |
| gemma3:4b | fbi_empathy | criminal_unstable | all | 90 | empathy: 36, threat: 0, deescalation: 4, escalation: 0 | calmness: 0.99 | 19/20 | 6 |

## Definitions

- **Release rate:** runs ending in `criminal_release` or `both` over completed runs; Wilson 95% interval. Failed and budget-aborted runs are excluded (count in brackets).
- **FBI concessions:** runs ending in `fbi_vehicle` or `both`.
- **First release turn:** the criminal message the FBI detected as a release (the turn before the FBI's first canned thank-you).
- **Latency:** median `latency_s` over LLM calls; median `execution_time_s` over runs (negotiation wall-clock, perplexity excluded). Local and API latency are not like-for-like.
- **max_tokens stops:** calls with stop reason `max_tokens` (Claude) or `length` (Ollama) / all calls.
- **Repetitive LLM turns (EV-8):** the original `_is_repetitive` (exact repeat, Jaccard > 0.6 against the speaker's last 3 replies, reused metaphor), per speaker, on the model's own text.
- **Self-contradicting release turns:** criminal turns whose canned prefix is a release line and whose LLM text matches `\b(van|vehicle)s?\b`, over all criminal turns with a canned release prefix.
- **Cost per run:** mean estimated cost from logged tokens and config prices; n/a for unpriced (local) models.
- **Detector hits:** the criminal persona's own regex detectors (as gated in `agents.py`) re-run on each non-empty FBI message it replied to. The state variable is calmness (unstable) or cooperation (calculated); above 0.7 the canned release line is prepended.
