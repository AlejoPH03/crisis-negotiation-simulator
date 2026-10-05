# Decisions

Every place where the spec was ambiguous, conflicted with the code, or needed a choice the spec does not make.
✱ marks a spec/code discrepancy that was **recorded, not fixed** (E1 and E2 must reproduce v0 behaviour).
"Agreed" means the choice was confirmed by the project owner on 2026-10-03.

## Setup

**D1. The tag already existed.** `v0-university` was already on commit `2831134` ("Original COMP3004 code"), which also contains `CLAUDE.md` and `docs/SPEC.md`. No new commit or tag was made for the original code, and history was not touched.

**D2. Virtual environment.** All installs and test runs use `.venv` in the repo (git-ignored). Agreed.

**D3. `results/` is git-ignored** (owner instruction). CLAUDE.md requires every README number to come from a file in `results/`, so the result files quoted in the README will need to be committed or published at Milestone 6.

## Milestone 1: clean baseline (E1)

**D4. The turn limit counts messages.** The v0 loop counts each agent's reply as a "round" (`rounds += 1` per message), and the spec's EV-3 says "Rounds = number of messages". `max_rounds: 10` therefore means 10 messages in total, 5 per agent. The v0 default of 8 (`max_rounds = 8`) is overridden by config, as FR-8 requires.

**D5. ✱ Ollama ignores `max_tokens`.** v0 passes `max_tokens: 150` in the Ollama `options` dict, but Ollama's token-limit option is `num_predict`, so `max_tokens` is most likely ignored and Gemma's replies were uncapped. E1 passes the options dict unchanged, for fidelity. Each LLM call logs `eval_count` (output tokens), so the E1 run shows whether replies exceed 150 tokens. Whether `frequency_penalty` and `presence_penalty` are applied also depends on the installed Ollama version. Not verified live.

**D6. Seeding (FR-11).** Only the canned-line RNG is seeded: each run gets `random.Random(run.seed + run_index)`, injected into both agents, and it replaces the global `random.choice`. LLM sampling is not seeded. Adding Ollama's `seed` option would change the v0 `ollama.chat` call, and the Claude API has no seed. Runs are therefore reproducible in their canned-line choices only. Because `random.Random(s)` produces the same sequence as `random.seed(s)` followed by `random.choice`, the equivalence test can compare against v0's global RNG directly.

**D7. Error handling (NF-2).** These are the only intended behaviour changes, and all of them are on error paths:
- v0's `except Exception: return "Error getting response."` is removed. LLM errors propagate and the run is logged as `status: "failed"`, with the error type, message and attempt count, plus the partial transcript.
- A missing message content from Ollama now raises an error, instead of returning v0's placeholder "No response received.".
- Rate-limit (429), 408/409, server errors (5xx, including 529 overloaded) and connection/timeout errors are retried with exponential backoff and jitter (config `retry`), and the `retry-after` header is honoured. Other 4xx errors are not retried.
- The Anthropic SDK's built-in retries are turned off (`max_retries=0`), so one logged retry policy applies to both backends.
- After `run.max_consecutive_failures` (3) consecutive failed runs, the experiment stops (`stopped_reason: max_consecutive_failures`). This stops an outage or a bad API key from burning through the whole grid.
- Programming errors (any exception that is not `LLMError` or `BudgetExceeded`) are not caught. They crash the runner after the earlier records have already been flushed to `runs.jsonl`. Until D23, the clients themselves wrapped every exception, so this rule only held outside the clients.
- A perplexity failure is logged as `perplexity: null` plus `perplexity_error`, instead of v0's `float('inf')`, which is not valid JSON.

**D8. `print` became `logging`; no logic changed.** The state-transition `try/except` in `FBIAgent.respond` and `CriminalAgent.respond` is kept (it is game logic, not the LLM path) and now logs a warning. The GPT-2 model in `metrics.py` loads on first use instead of at import. The perplexity computation itself (whole transcript, 512-token truncation) is unchanged.

**D9. Equivalence proof.** `tests/v0_reference/` is a byte-for-byte copy of `src/` at the tag. `test_v0_reference_matches_tag.py` checks it against `git show v0-university:...`, normalising line endings for `core.autocrlf`. `test_equivalence.py` runs both versions on the same scripted replies and seeds:
- all 8 configurations,
- 5 hand-written scripts plus 25 random scripts, with 2 seeds each,
- identical history, transcript, concessions and rounds required,
- identical LLM requests required (system prompt plus messages, temperature, max_tokens),
- with the real `OllamaClient`: identical `ollama.chat` arguments required (model, messages, options dict).

As a sanity check, changing one threshold or one canned line makes the test fail.

**D10. ✱ v0 game-logic quirks, kept as is** (pinned in `tests/test_characterization.py` unless noted):
- **(a)** When the FBI detects a release (`FBIAgent._check_agreement`), it moves to `AwaitAgreementState`, not `EndState`, so the run continues. The FBI's next turn calls the LLM and only then reaches `EndState`. But if the criminal's next reply again contains a release (the unstable criminal's calm canned line repeats it every turn), the FBI answers with the canned thank-you again and stays in `AwaitAgreementState`. In that case the run goes to the turn limit. This inflates rounds-to-outcome (EV-3) for release outcomes. The criminal side behaves the same way after a vehicle concession.
- **(b)** `NegotiateState.next_state` runs `_check_agreement` on the agent's own reply. An FBI reply that matches the release regex, or a criminal reply that matches the vehicle regex, moves that agent to `AwaitAgreementState` with no agreed demand, which ends the run early with no concession. (Covered by the hand-written scripts in the equivalence test.)
- **(c)** `_detect_authority` is never called, so authority language has no direct effect on the unstable criminal. The spec's "Detector gating" row implies it does. Authoritative language can still move the unstable criminal through `_detect_threat` and `_detect_escalation`.
- **(d)** `_update_strategic_state` (calculated) applies its decay before the detectors; `_update_emotional_state` (unstable) applies it after.
- **(e)** `_detect_threat`'s 10 patterns are the first 10 of `_detect_escalation`, so one threatening message costs the unstable criminal −0.3 and −0.2 calmness.
- **(f)** `_detect_logical_threats` contains very broad patterns, `\b(?:prison|jail|sentence|time)\b` and `\b(?:the|this)\s+(?:situation|circumstances|conditions)\b`, so almost any message mentioning "time" or "the situation" counts as a logical threat (+0.2 cooperation). It also contains every vehicle-delay pattern, so a delay message counts as both: +0.2 then −0.2 cooperation, a net −0.01 after decay.
- **(g)** The empathy prompt tells the FBI to say "I understand you're scared", but `_detect_empathy` only matches "you **are** scared", so the contraction the prompt asks for is not detected.
- **(h)** The FBI's canned "I will provide you with an unmarked vehicle." (`BaseAgent.get_acknowledgement_message`) is only reachable through `BaseAgent.respond`, which `FBIAgent` overrides. An FBI vehicle concession therefore depends entirely on the LLM's own wording matching the criminal's regex.
- **(i)** Unreachable code is kept as is: `BaseAgent.respond`, the FSM `handle()` methods (including the 5-message history and the `_is_repetitive` retry loop), `CheckProgressState`, `detect_timeout` and `is_negotiation_complete`. The unstable criminal's `strategic_state` fallback is unreachable too.

**D11. Runs per configuration.** 10 per configuration (spec rule 2) → 80 runs per condition. Grid order matches v0: FBI persona → criminal persona → starting role → trial.

**D12. Hardware is recorded per run** (platform, CPU, Python) for EV-4. GPU details for the Ollama host are not visible to the runner.

## Milestone 2: model swap (E2)

**D13. Claude `max_tokens` is 300** (agreed). The personas ask for 120 words or fewer (about 160 tokens), and Gemma was most likely uncapped (D5), so 150 would have truncated Claude where Gemma was not. `stop_reason` is logged for every call, so `max_tokens` truncations are counted. Only temperature (0.6) is held constant across backends. Claude gets no top_k, top_p or penalties.

**D14. Neutral opening user turn, Claude only.** The Messages API needs a user message first. When an agent speaks first (no previous message), `ClaudeClient` sends the user turn `"(The phone line connects. You speak first.)"` (config `llm.opening_user_message`). The same rule applies if a message list ever starts with an assistant turn, and consecutive same-role turns are merged; neither happens in `last_message` mode. Ollama is unchanged: v0 sent the system prompt alone, and still does. The system prompt (persona plus demands status plus, when there is no previous message, the anti-repetition line) goes in the API `system` parameter.

**D15. Budget cap (NF-1).** The cap applies per invocation of `experiment`, `negotiate` or `smoke`. It is checked before every LLM call and before every run. When spend reaches the cap, the in-flight run is logged as `aborted_budget` with its partial transcript, and the runner stops (`stopped_reason: budget_cap`). Spend can overshoot by at most one call. Prices are in USD per million tokens, from Anthropic's published rates (Haiku 4.5: $1/$5, Sonnet 4.6: $3/$15). The £ conversion in EV-11 is deferred to Milestone 5. Caps are $5 for E2 and $5 for E0 (agreed). Every Claude model in a config must have a price, or the config is rejected. Dry runs report "(dry-run)" model names, which have no price, so they cost nothing.

**D16. API key.** The key is read only from `ANTHROPIC_API_KEY` (NF-4). The CLI calls `python-dotenv` with `override=False`, which only fills that environment variable from a local `.env` file. The key is never logged, and `ClaudeClient.__repr__` does not include it.

**D17. Paid runs ask first.** `experiment`, `negotiate` and `smoke` on the Claude backend show the run count, models and cap, and wait for `y` before starting. `--yes` skips the prompt and `--dry-run` never calls any backend.

**D21. Temperature is sent through `extra_body` (2026-10-03, after the first live E2 attempt).** The live E2 run failed on every call with `TypeError: Messages.create() got an unexpected keyword argument 'temperature'`. The installed `anthropic` 1.11.0 removed `temperature`, `top_p` and `top_k` from the `messages.create()` signature (confirmed with `inspect.signature`). They are gone from the SDK, not from the API: Haiku 4.5 and Sonnet 4.6 still accept `temperature`. To keep FR-8 (temperature 0.6 in every condition), `ClaudeClient` now sends `extra_body={"temperature": temperature}`, which the SDK merges into the request JSON as a top-level `temperature` field. Nothing else about the request changed.
- **Why the mocked tests missed it:** the fake SDK accepted any keyword. It now binds every call to the installed `Messages.create` signature, so an unsupported keyword fails the test the same way the SDK does.
- **New tests:** one runs the real SDK's request building through a mock HTTP transport (no network) and checks the JSON body. Another runs a full E2 experiment through that path and checks cost.
- **Pin:** `requirements.txt` pins `anthropic>=1.11.0,<2`.
- **Note:** models that reject non-default sampling (Opus 4.7 and later, Sonnet 5 and 5.5) would return a 400 error here. E5's model choice must account for this (see D19).
- **How the failure was logged:** the `TypeError` happened inside the client, whose catch-all turns any exception into a non-retryable `LLMError`. So the runs were logged as `failed` and the experiment stopped after 3, rather than crashing. That contradicts D7's "programming errors are not caught". The owner decided the clients should wrap only SDK and transport errors; see D23.

**D22. Cost reporting fix.** After that failed run, the summary said "Cost: n/a (no prices for this model)" although `claude-haiku-4-5` is priced. The price lookup was not at fault: costs are keyed by the configured model ID, and a test now confirms that the dated ID returned by the API (`claude-haiku-4-5-20251001`) does not affect it. The cause was that `cost_usd` was set to `null` whenever a run made no completed calls, and the CLI printed every `null` as "no prices". Now a run on a priced model reports the sum of its call costs, which is `0.0` when no call completed. `null` means only that the model has no price (Ollama, or a dry run).

**D23. Clients wrap only SDK, HTTP and connection errors** (owner decision, 2026-10-03; closes the question in D21). Both clients now catch a fixed list of exceptions and turn those into `LLMError`, with the same retry rules as before:
- **`OllamaClient`:**
  - `ollama.ResponseError`: retried on 429 and 5xx, not on other statuses.
  - The built-in `ConnectionError` (what ollama raises when the server is unreachable) and `httpx.TransportError`: retried.
  - `ollama.RequestError` and other `httpx.HTTPError`: not retried.
- **`ClaudeClient`:**
  - `anthropic.APIStatusError`: retried on 408, 409, 429 and 5xx, honouring `retry-after`; not on other statuses.
  - `anthropic.APIConnectionError` and timeouts: retried. Raw `httpx2.TransportError` is also retried; before, it was not.
  - Any other `anthropic.AnthropicError` and `httpx2.HTTPError`: not retried.

Every other exception (`TypeError`, `AttributeError`, `KeyError` and so on) is a bug. It is not retried, it does not become a `failed` run, and it raises out of the experiment, so D7's rule now holds inside the clients too. The bug in D21 would now have stopped the first run with a traceback, instead of writing three `failed` records.
- **Tests:** in each client, a `TypeError`, `AttributeError`, `KeyError` or `ValueError` raises unchanged, after one call. A full E1 or E2 experiment whose client raises a `TypeError` exits with that `TypeError` and writes no `failed` record. Other SDK and HTTP errors are still wrapped, with the retry rules above.
- **Unchanged:** a missing message content in an Ollama response is still a deliberate non-retryable `LLMError` (D7). The equivalence test against v0 (566 cases) still passes.

## Milestone 0: smoke test (E0)

**D18. E0 design** (agreed). The spec table lists E0 as "Memory: Full, detection n/a". The owner chose to run the **E2 pipeline** (last-message memory, regex detectors, canned lines) on two models instead.
- Models: `claude-haiku-4-5` and `claude-sonnet-4-6`.
- Each criminal persona runs 5 times against each FBI persona, per model: 40 runs.
- The starting role alternates by trial (fbi, criminal, fbi, criminal, fbi), so both openings and the opening-turn rule are exercised.

**D19. Sonnet 4.6, not Sonnet 5.5** (agreed). Sonnet 5.5 returns a 400 error for any non-default temperature, which would break FR-8. Sonnet 4.6 accepts temperature 0.6 and has thinking off by default. E5's model is still to be decided.

**D20. E0 flags are heuristics, not verdicts.** They run on Claude's own text only; the canned prefixes are excluded. The flags are `refusal`, `ai_disclosure`, `out_of_character`, `empty_reply`, `truncated` and `criminal_no_threat_language` (a hint at softened threats). The owner judges the transcripts.

**D24. E0 result: Haiku 4.5 fails, Sonnet 4.6 passes, and E2 is rerun on Sonnet** (owner verdict, 2026-10-05).
- **Source:** `results/e0/20261003-172725/` (config hash `5a3e17f0…`, 40/40 runs completed, $1.1592). Flag counts are from `runs.jsonl`; truncation counts are from the call stop reasons.
  - `claude-haiku-4-5`: `refusal` and `out_of_character` on 20/20 runs, `truncated` on 20/20 runs, `ai_disclosure` on 4/20, `criminal_no_threat_language` on 9/20. 123 of 192 calls (64.1%) stopped at `max_tokens`.
  - `claude-sonnet-4-6`: `refusal` on 1/20 runs, `criminal_no_threat_language` on 12/20, no other flags. 0 of 188 calls stopped at `max_tokens`.
- **Verdict:** the owner read the transcripts and judged Haiku a fail and Sonnet a pass. The flags are heuristics (D20); the pass verdict covers Sonnet's flagged runs.
- **E2 on Haiku is kept as a documented negative result.** `results/e2/20261004-235415/` (config hash `5b937234…`, `configs/e2_haiku.yaml`): 80/80 runs completed, $1.590263, and 482 of 789 calls (61.1%) stopped at `max_tokens` (300, D13). Neither the config nor the results are deleted.
- **E2 is rerun on Sonnet** with `configs/e2_sonnet.yaml`: identical to `e2_haiku.yaml` except `model: claude-sonnet-4-6`, its price ($3/$15 per million tokens), `output_dir: results/e2_sonnet` and `cap_usd: 6.00`. A test enforces that these are the only differences. For scale, E0 spent $0.774 on 20 Sonnet runs.
- **✱ Conflict with the spec:** the spec's condition table puts E2, E3 and E4 on Claude Haiku and makes E5 "one tier up" on Sonnet. With E2 on Sonnet, the E3 and E4 model and the meaning of E5 must be decided before Milestone 3. **Open question for the owner.**
- **Not tested:** whether Haiku's high truncation rate at `max_tokens` 300 contributed to its E0 flags. A run with a higher cap would answer it.
- **README:** the spec asks for an E0 failure to be recorded in the README. That is due at Milestone 6.

## Analysis tooling

**D25. Results analysis script** (`python -m src analyze <folder> [...] [--by-start]`). It reads only `runs.jsonl` and writes `analysis.md` and `analysis.json` into the same folder. Groups are model × FBI persona × criminal persona, pooled over starting role (split with `--by-start`), plus a total row per model. Definitions:
- **Release rate:** outcome `criminal_release` or `both`, over completed runs, with a Wilson 95% score interval. Failed and budget-aborted runs are excluded and their count is reported.
- **Turn of first release:** the criminal message the FBI detected as a release, i.e. the turn just before the FBI's first canned thank-you, which is its only canned reply. Reported as median (min–max).
- **Median perplexity:** of the per-run values (EV-5), with n.
- **Median latency:** per call (`latency_s`) and per run (`execution_time_s`, the negotiation's wall-clock time, perplexity excluded).
- **max_tokens stop rate:** calls stopped at the token limit, over all calls. For Claude the stop reason is `max_tokens`; for Ollama it is `length`, so the metric is comparable across backends.
- **Self-contradicting release turns:** criminal turns whose canned prefix is one of the two release lines and whose LLM text matches `(van|vehicle)s?` (case-insensitive, whole words). Reported over all criminal turns with a canned release prefix. A test checks the release lines against `agents.py`.

**Added 2026-10-05 for the README:**
- **FBI concessions:** count of runs ending in `fbi_vehicle` or `both`.
- **Cost per run:** mean of `cost_usd`, which is n/a for unpriced (local) models.
- **Repetition (EV-8):** the original `BaseAgent._is_repetitive` (exact repeat, Jaccard > 0.6 against the speaker's last 3 replies, reused metaphor), applied per speaker to the model's own text, with the same state updates as `NegotiateState.handle`.
- **Detector hits:** each criminal persona's own detectors, with its gating, re-run on the non-empty FBI messages it replied to. Only the detectors that `_update_*_state` actually calls are used, so `_detect_authority` is excluded. Also the highest calmness or cooperation reached, and the runs above 0.7.
- **Optional `--phrase` counts:** FBI messages the criminal received that contain the phrase (case-insensitive, whole word).
- **`python -m src transcript <folder> --run-index N --out <file>`:** renders one logged run as Markdown with the E0 renderer. The text is exactly as logged.

`analysis.md` shows values to 3 decimals; `analysis.json` keeps full precision. On the three live folders, the script's release and truncation counts match the independent counts in each `summary.json`.

## README and evidence

**D26. Committed evidence and README wording** (2026-10-05).
- **Force-added files:** `results/` stays git-ignored (D3). Only the files the README cites are force-added:
  - `summary.json`, `runs.jsonl`, `config.yaml`, `analysis.md` and `analysis.json` for E1 (`results/e1/20261004-005801`), E2 Haiku (`results/e2/20261004-235415`) and E2 Sonnet (`results/e2_sonnet/20261005-014815`);
  - for E0 (`results/e0/20261003-172725`): `summary.md`, `config.yaml`, `analysis.md` and `analysis.json`.

  `config.yaml` is included because CLAUDE.md requires every README number to come with its config. E0's `runs.jsonl` and per-run transcripts are not committed, so E0's `summary.md` links to transcript files that aren't in the repo, and its analysis can't be regenerated from the repo alone.
- **Examples** are rendered from E2 Sonnet `runs.jsonl` with `python -m src transcript`, using a fixed rule: the first run in run order for each case. Release: authority → calculated, `run_index` 60. No release: empathy → unstable, `run_index` 0.
- **Every README number** comes from `analysis.md` or `analysis.json` (written by `python -m src analyze ... --phrase "I hear you"`) or from the committed `summary.json` and `summary.md`.
- **Two claims the README avoids:**
  - **"Gemma's phrasing":** the empathy detector was "tuned to Gemma's phrasing" is supported by the code comment "based on actual FBI responses" and by the original project running Gemma. That is an inference, not a measured fact.
  - **"Caught before scaling up":** the README doesn't say the smoke test caught Haiku before scaling up, because the full 80-run Haiku E2 (`20261004-235415`) ran after E0 (`20261003-172725`) and before the verdict was recorded. It says E0 flagged the problem at 40 runs and $1.16, and the full Haiku run confirmed it.
