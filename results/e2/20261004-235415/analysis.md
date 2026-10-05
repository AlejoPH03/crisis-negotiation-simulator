# Analysis of `results/e2/20261004-235415`

Condition(s): E2. Runs: 80. Config hash(es): 5b9372341f9ccb90b70c216ff1e77993291757ea96a80591fb0a940dc97ea577.
Computed by `python -m src analyze` from `runs.jsonl`. Values shown to 3 decimals (cost to 4); `analysis.json` has full precision.

## Outcomes and quality

| Model | FBI | Criminal | Starts | Completed (excl.) | Releases | Release rate [Wilson 95% CI] | FBI concessions | First release turn: median (min-max) | Median perplexity (n) | Median latency per call / per run (s) | max_tokens stops | Repetitive LLM turns | Self-contradicting release turns | Cost per run (mean) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| claude-haiku-4-5 | fbi_authority | criminal_calculated | all | 20 (0) | 1 | 0.050 [0.009, 0.236] | 0 | 9 (9-9) | 42.428 (20) | 4.213 / 40.293 | 117/199 (0.588) | 1/199 (0.005) | 0/2 | $0.0198 |
| claude-haiku-4-5 | fbi_authority | criminal_unstable | all | 20 (0) | 0 | 0.000 [0.000, 0.161] | 0 | n/a | 44.694 (20) | 4.105 / 39.911 | 132/200 (0.660) | 5/200 (0.025) | 0/0 | $0.0202 |
| claude-haiku-4-5 | fbi_empathy | criminal_calculated | all | 20 (0) | 3 | 0.150 [0.052, 0.360] | 0 | 8 (4-8) | 37.017 (20) | 4.154 / 39.060 | 106/190 (0.558) | 2/190 (0.011) | 0/8 | $0.0190 |
| claude-haiku-4-5 | fbi_empathy | criminal_unstable | all | 20 (0) | 0 | 0.000 [0.000, 0.161] | 0 | n/a | 37.993 (20) | 4.201 / 39.988 | 127/200 (0.635) | 6/200 (0.030) | 0/0 | $0.0206 |
| **claude-haiku-4-5** | **ALL** | **ALL** | all | 80 (0) | 4 | 0.050 [0.020, 0.122] | 0 | 8.0 (4-9) | 40.626 (80) | 4.180 / 39.872 | 482/789 (0.611) | 14/789 (0.018) | 0/10 | $0.0199 |

## Detector hits on the FBI messages the criminal received

| Model | FBI | Criminal | Starts | FBI messages received | Detector hits | State variable: max reached | Runs above 0.7 | FBI messages containing "I hear you" |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| claude-haiku-4-5 | fbi_authority | criminal_calculated | all | 90 | logical_threats: 31, vehicle_delay: 1, deescalation: 0, escalation: 0 | cooperation: 0.86 | 2/20 | 0 |
| claude-haiku-4-5 | fbi_authority | criminal_unstable | all | 90 | empathy: 0, threat: 0, deescalation: 0, escalation: 0 | calmness: 0.30 | 0/20 | 0 |
| claude-haiku-4-5 | fbi_empathy | criminal_calculated | all | 87 | logical_threats: 23, vehicle_delay: 2, deescalation: 1, escalation: 0 | cooperation: 0.86 | 3/20 | 4 |
| claude-haiku-4-5 | fbi_empathy | criminal_unstable | all | 90 | empathy: 1, threat: 0, deescalation: 0, escalation: 0 | calmness: 0.67 | 0/20 | 1 |

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
