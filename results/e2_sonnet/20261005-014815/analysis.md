# Analysis of `results/e2_sonnet/20261005-014815`

Condition(s): E2. Runs: 80. Config hash(es): 18f4f743b54efe91f037ef558c50da5fe3a331c18dd53fe2c3f568406719e5c4.
Computed by `python -m src analyze` from `runs.jsonl`. Values shown to 3 decimals (cost to 4); `analysis.json` has full precision.

## Outcomes and quality

| Model | FBI | Criminal | Starts | Completed (excl.) | Releases | Release rate [Wilson 95% CI] | FBI concessions | First release turn: median (min-max) | Median perplexity (n) | Median latency per call / per run (s) | max_tokens stops | Repetitive LLM turns | Self-contradicting release turns | Cost per run (mean) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| claude-sonnet-4-6 | fbi_authority | criminal_calculated | all | 20 (0) | 19 | 0.950 [0.764, 0.991] | 0 | 7 (6-9) | 35.654 (20) | 5.377 / 42.487 | 0/162 (0.000) | 0/162 (0.000) | 42/42 | $0.0314 |
| claude-sonnet-4-6 | fbi_authority | criminal_unstable | all | 20 (0) | 0 | 0.000 [0.000, 0.161] | 0 | n/a | 29.879 (20) | 5.508 / 55.085 | 0/199 (0.000) | 0/199 (0.000) | 0/0 | $0.0422 |
| claude-sonnet-4-6 | fbi_empathy | criminal_calculated | all | 20 (0) | 8 | 0.400 [0.219, 0.613] | 0 | 7.0 (6-9) | 26.601 (20) | 5.159 / 49.908 | 0/182 (0.000) | 0/182 (0.000) | 17/17 | $0.0364 |
| claude-sonnet-4-6 | fbi_empathy | criminal_unstable | all | 20 (0) | 1 | 0.050 [0.009, 0.236] | 0 | 6 (6-6) | 23.748 (20) | 5.213 / 52.340 | 0/198 (0.000) | 0/198 (0.000) | 0/0 | $0.0428 |
| **claude-sonnet-4-6** | **ALL** | **ALL** | all | 80 (0) | 28 | 0.350 [0.255, 0.459] | 0 | 7.0 (6-9) | 28.254 (80) | 5.325 / 51.325 | 0/741 (0.000) | 0/741 (0.000) | 59/59 | $0.0382 |

## Detector hits on the FBI messages the criminal received

| Model | FBI | Criminal | Starts | FBI messages received | Detector hits | State variable: max reached | Runs above 0.7 | FBI messages containing "I hear you" |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| claude-sonnet-4-6 | fbi_authority | criminal_calculated | all | 87 | logical_threats: 59, vehicle_delay: 0, deescalation: 0, escalation: 0 | cooperation: 0.87 | 19/20 | 3 |
| claude-sonnet-4-6 | fbi_authority | criminal_unstable | all | 89 | empathy: 0, threat: 0, deescalation: 0, escalation: 0 | calmness: 0.30 | 0/20 | 47 |
| claude-sonnet-4-6 | fbi_empathy | criminal_calculated | all | 88 | logical_threats: 55, vehicle_delay: 14, deescalation: 4, escalation: 0 | cooperation: 0.87 | 9/20 | 65 |
| claude-sonnet-4-6 | fbi_empathy | criminal_unstable | all | 89 | empathy: 0, threat: 0, deescalation: 0, escalation: 0 | calmness: 0.30 | 0/20 | 75 |

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
