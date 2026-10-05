# Analysis of `results/e0/20261003-172725`

Condition(s): E0. Runs: 40. Config hash(es): 5a3e17f0ffa0e1ba034b8fc9046421a2f7aafb311f238814afe11287a14e0d8b.
Computed by `python -m src analyze` from `runs.jsonl`. Values shown to 3 decimals (cost to 4); `analysis.json` has full precision.

## Outcomes and quality

| Model | FBI | Criminal | Starts | Completed (excl.) | Releases | Release rate [Wilson 95% CI] | FBI concessions | First release turn: median (min-max) | Median perplexity (n) | Median latency per call / per run (s) | max_tokens stops | Repetitive LLM turns | Self-contradicting release turns | Cost per run (mean) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| claude-haiku-4-5 | fbi_authority | criminal_calculated | all | 5 (0) | 2 | 0.400 [0.118, 0.769] | 0 | 4.0 (2-6) | n/a (0) | 4.125 / 38.574 | 26/42 (0.619) | 1/42 (0.024) | 0/3 | $0.0160 |
| claude-haiku-4-5 | fbi_authority | criminal_unstable | all | 5 (0) | 0 | 0.000 [0.000, 0.434] | 0 | n/a | n/a (0) | 4.092 / 39.628 | 33/50 (0.660) | 1/50 (0.020) | 0/0 | $0.0203 |
| claude-haiku-4-5 | fbi_empathy | criminal_calculated | all | 5 (0) | 0 | 0.000 [0.000, 0.434] | 0 | n/a | n/a (0) | 4.153 / 39.967 | 28/50 (0.560) | 2/50 (0.040) | 0/0 | $0.0202 |
| claude-haiku-4-5 | fbi_empathy | criminal_unstable | all | 5 (0) | 0 | 0.000 [0.000, 0.434] | 0 | n/a | n/a (0) | 4.188 / 40.053 | 36/50 (0.720) | 0/50 (0.000) | 0/0 | $0.0206 |
| **claude-haiku-4-5** | **ALL** | **ALL** | all | 20 (0) | 2 | 0.100 [0.028, 0.301] | 0 | 4.0 (2-6) | n/a (0) | 4.153 / 39.727 | 123/192 (0.641) | 4/192 (0.021) | 0/3 | $0.0193 |
| claude-sonnet-4-6 | fbi_authority | criminal_calculated | all | 5 (0) | 5 | 1.000 [0.566, 1.000] | 0 | 7 (6-8) | n/a (0) | 5.436 / 43.625 | 0/41 (0.000) | 0/41 (0.000) | 12/12 | $0.0317 |
| claude-sonnet-4-6 | fbi_authority | criminal_unstable | all | 5 (0) | 0 | 0.000 [0.000, 0.434] | 0 | n/a | n/a (0) | 5.486 / 54.931 | 0/50 (0.000) | 0/50 (0.000) | 0/0 | $0.0424 |
| claude-sonnet-4-6 | fbi_empathy | criminal_calculated | all | 5 (0) | 1 | 0.200 [0.036, 0.624] | 0 | 5 (5-5) | n/a (0) | 5.177 / 51.580 | 0/47 (0.000) | 0/47 (0.000) | 4/4 | $0.0376 |
| claude-sonnet-4-6 | fbi_empathy | criminal_unstable | all | 5 (0) | 0 | 0.000 [0.000, 0.434] | 0 | n/a | n/a (0) | 5.271 / 52.663 | 0/50 (0.000) | 0/50 (0.000) | 0/0 | $0.0431 |
| **claude-sonnet-4-6** | **ALL** | **ALL** | all | 20 (0) | 6 | 0.300 [0.145, 0.519] | 0 | 6.5 (5-8) | n/a (0) | 5.343 / 52.076 | 0/188 (0.000) | 0/188 (0.000) | 16/16 | $0.0387 |

## Detector hits on the FBI messages the criminal received

| Model | FBI | Criminal | Starts | FBI messages received | Detector hits | State variable: max reached | Runs above 0.7 | FBI messages containing "I hear you" |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| claude-haiku-4-5 | fbi_authority | criminal_calculated | all | 20 | logical_threats: 9, vehicle_delay: 1, deescalation: 0, escalation: 0 | cooperation: 0.87 | 1/5 | 0 |
| claude-haiku-4-5 | fbi_authority | criminal_unstable | all | 23 | empathy: 0, threat: 0, deescalation: 0, escalation: 0 | calmness: 0.30 | 0/5 | 0 |
| claude-haiku-4-5 | fbi_empathy | criminal_calculated | all | 23 | logical_threats: 8, vehicle_delay: 1, deescalation: 0, escalation: 0 | cooperation: 0.67 | 0/5 | 1 |
| claude-haiku-4-5 | fbi_empathy | criminal_unstable | all | 23 | empathy: 0, threat: 0, deescalation: 0, escalation: 0 | calmness: 0.30 | 0/5 | 0 |
| claude-sonnet-4-6 | fbi_authority | criminal_calculated | all | 23 | logical_threats: 15, vehicle_delay: 0, deescalation: 0, escalation: 0 | cooperation: 0.87 | 5/5 | 2 |
| claude-sonnet-4-6 | fbi_authority | criminal_unstable | all | 23 | empathy: 0, threat: 0, deescalation: 0, escalation: 0 | calmness: 0.30 | 0/5 | 15 |
| claude-sonnet-4-6 | fbi_empathy | criminal_calculated | all | 23 | logical_threats: 14, vehicle_delay: 4, deescalation: 1, escalation: 0 | cooperation: 0.85 | 2/5 | 18 |
| claude-sonnet-4-6 | fbi_empathy | criminal_unstable | all | 23 | empathy: 1, threat: 0, deescalation: 0, escalation: 0 | calmness: 0.67 | 0/5 | 18 |

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
