# Crisis Negotiation Simulator: Claude Rebuild Spec (v2)

Oct 1, 2026 · @Alejandro · v2, based on the `DIA_CODE` source and the COMP3004 report

## Purpose and goals

Rebuild the COMP3004 crisis negotiation simulator on the Claude API, measure it against a fresh Gemma 3 baseline, and test whether the original headline finding holds up. The result should support one CV bullet with real before-and-after numbers.

- **G1.** Run the existing hostage scenario with Claude-powered agents, end to end.
- **G2.** Separate the effect of the **model** from the effect of the **architecture**, with a fair, measured comparison against a rerun Gemma 3 baseline.
- **G3.** Show hands-on use of the Claude API: system prompts, multi-turn state, tool use, and LLM-based classification and evaluation.
- **G4.** Test whether the report's 2×2 finding (empathy works on the unstable criminal, authority works on the calculated one) still appears when the outcome is not decided by hand-written rules.
- **G5.** Publish a clean public repo that a reviewer can understand in five minutes.

## What the original system actually does

This section records the baseline as implemented in the code, because it differs from the report in places. Where they disagree, the code is treated as the source of truth and the rerun baseline (E1) replaces the report's numbers.

| Component | What the code does | What the report says | Implication for the rebuild |
| --- | --- | --- | --- |
| Model | `gemma3:4b` via `ollama.chat`, temperature 0.6, top_k 50, top_p 0.95. `max_tokens` and penalties are passed as Ollama options. | Gemma 3 via Ollama | Verify which options Ollama actually applied (its token limit option is `num_predict`). Hold only temperature constant across backends. |
| Scenario | Lima National Bank, 5 hostages including a pregnant one. FBI demand: release the pregnant hostage. Criminal demand: an unmarked vehicle. One demand per side. | Same | Keep unchanged. |
| Design | 2 FBI personas × 2 criminal personas × 2 starting roles = 8 configurations | Same | Keep the full 2×2×2 design. |
| Turn limit | `max_rounds = 8` | 10 rounds | Pick one value for every condition (10, to match the report) and record it. |
| Trials | `n_trials = 1` | n = 3 | The reported results can't be regenerated from this code as is. E1 becomes the canonical baseline. |
| Agent memory | Each LLM call receives only the system prompt and the opponent's last message. The FSM handlers that pass the last 5 messages are bypassed because `FBIAgent` and `CriminalAgent` override `respond()`. | Agents keep a history | Agents effectively have one turn of memory. Full history must be a separate, measured change. |
| Outcome decision | The criminal's numeric state (unstable: calmness, anxiety, anger; calculated: cooperation, pressure, patience) is updated by regex detectors on the FBI's message. Above 0.7, a canned line is prepended to the LLM text, e.g. "I'm ready to cooperate. I will release the pregnant hostage." The FBI's regex `_check_agreement` then detects it. | Points-based state transitions | Outcomes are decided by the rule engine, with the LLM's language mattering only through detector hits. |
| Detector gating | `_detect_empathy` and `_detect_authority` only run for the unstable criminal. `_detect_logical_threats` and `_detect_vehicle_delay` only run for the calculated criminal. | Not mentioned | The 2×2 finding is partly built into the rules: empathy can only calm the unstable persona, and logical threats can only move the calculated one. G4 tests this directly. |
| Agreement detection | Negation-aware regex on both sides | Regex plus an embedding-based paraphrase checker (SentenceTransformers) | There is no embedding detector in the code. Don't claim one anywhere (CV, README, interviews). |
| Repetition control | `_is_repetitive` and the metaphor filter exist, but are only called from `NegotiateState.handle`, which the live path never reaches. The anti-repetition instruction is only appended when the last message is the system prompt. | Active repetition filtering | Repetition control was effectively off. Measure repetition as a metric instead of claiming a fix. |
| Response assembly | Criminal replies are a canned line followed by free LLM text. | Not mentioned | A reply can contradict itself (canned release, then the LLM keeps demanding). Count this as a rule violation. |
| Metrics | GPT-2 perplexity on the whole transcript, truncated to 512 tokens. Rounds = number of messages. Wall-clock time via `@timer`. Outcome = which side's demand was agreed. | Same, minus the truncation | Keep for continuity and note the truncation. Add an LLM judge. |
| Packaging | `__init__.py` imports `prompts.py`, `compute_success_rate`, `compute_efficiency` and `check_success`, none of which exist in the source (`prompts.py` survives only as a `.pyc`). No requirements file, tests or results CSV. | n/a | Fix imports, add `requirements.txt`, and tag the original as `v0-university` before refactoring. |

## Scope

Keep the scenario, personas and core metrics. Change the model layer, agent memory, how actions are taken, how tactics are detected, and how outcomes are decided, each as a separate measured step.

| Area | Keep | Change |
| --- | --- | --- |
| Scenario and demands | Lima National Bank, single demand per side | None |
| 2×2×2 design | All 8 configurations | None |
| 4 personas | Same characters, traits and constraints | Static persona text moved into versioned prompt files and the API `system` parameter. Dynamic "Current Demands Status" moved into the latest user turn. |
| Model backend | `gemma3:4b` via Ollama as baseline | Claude added behind a shared `LLMClient` interface |
| Memory | Last-message mode kept for E1 and E2 | Full per-agent history in E3 onwards |
| Tactic detection | 7 regex detectors kept for E1 and E2 and as a cross-check | LLM classifier in E3 onwards |
| Actions and outcomes | Canned lines plus regex agreement detection for E1 and E2 | Structured tool calls in E3 onwards. The rule engine decides which actions are legal; the model decides whether to take them. |
| Evaluation | Concessions, perplexity, rounds, execution time | Add LLM judge, rule violations, refusals, repetition, detector agreement, tool validity, cost |

Out of scope: a web UI, fine-tuning, multi-demand scenarios, and agents that negotiate with real people.

## Experimental conditions

Each condition changes one thing from the one before it, so every difference in results has a single cause.

| ID | Condition | Backend | Memory | Tactic detection | Outcome decided by | Question it answers |
| --- | --- | --- | --- | --- | --- | --- |
| E0 | Refusal and character smoke test | Claude Haiku and Sonnet | Full | n/a | n/a | Will Claude play both criminal personas, threats included, without refusing or breaking character? |
| E1 | Baseline rerun | `gemma3:4b` | Last message | Regex | Rule engine plus canned lines | What does the original system actually score? |
| E2 | Model swap | Claude Haiku | Last message | Regex | Rule engine plus canned lines | What changes when only the model changes? |
| E3 | Architecture upgrade | Claude Haiku | Full history | LLM classifier | Rule engine gates tools, model calls them | What do memory, tools and better detection add? |
| E4 | LLM-decided outcomes | Claude Haiku | Full history | Logged only | The model, with no thresholds | Does the 2×2 pattern appear without hand-written rules? |
| E5 | Model tier comparison | Claude Sonnet | As E3 | As E3 | As E3 | What do quality, cost and latency look like one tier up? |

E0 gate: run each criminal persona 5 times against each FBI persona on both Claude tiers. Pass if there are no refusals, character breaks or softened threats that change the scenario. If it fails, decide on an adapted scenario before building anything else, record the decision in the README, and update the CV wording to match.

## Functional requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-1 | Define one `LLMClient` interface, `generate(system, messages, tools=None, temperature, max_tokens)`, returning text, tool calls, token usage and latency. Two implementations: `OllamaClient` (`gemma3:4b`) and `ClaudeClient` (Anthropic Python SDK). | Must |
| FR-2 | Select backend, model, memory mode, detection mode and decision mode from one YAML config per condition, not from code. | Must |
| FR-3 | Move the 4 personas into versioned files (e.g. `prompts/fbi_empathy.v1.md`). Keep the persona text static and pass the dynamic demands status in the latest user turn, so both backends see identical content and the system prompt stays cacheable. | Must |
| FR-4 | Support two memory modes: `last_message` (original behaviour, E1 and E2) and `full_history` (E3 onwards), with the opponent's turns arriving as `user` messages. | Must |
| FR-5 | In E3 onwards, agents speak in text and act through tools. FBI: `provide_vehicle()`, `stall_vehicle(reason)`. Criminal: `release_pregnant_hostage()`, `threaten_hostage(target, severity)`. Both: `end_negotiation(reason)`. | Must |
| FR-6 | Validate every tool call against the rule engine. In E3, `release_pregnant_hostage` is legal only once the criminal's state passes its threshold. In all tool conditions, `provide_vehicle` is legal only after a `threaten_hostage` call targeting the pregnant hostage, which enforces the FBI prompt rule "never offer vehicle without a clear pregnant-hostage threat". An invalid call returns an error `tool_result`; the agent may retry at most 2 times, and every rejection is logged. | Must |
| FR-7 | In E3 and E5, replace the 7 regex detectors (`_detect_empathy`, `_detect_authority`, `_detect_threat`, `_detect_deescalation`, `_detect_escalation`, `_detect_logical_threats`, `_detect_vehicle_delay`) with one classifier call (Claude Haiku, a tool with one boolean per tactic). Its output feeds the same score updates and the same persona gating as the original, so only detection quality changes. | Must |
| FR-8 | Apply one turn limit (10) and one temperature (0.6) to every condition. | Must |
| FR-9 | In E4, remove the thresholds and canned lines: `release_pregnant_hostage` is always available, and the persona prompt alone describes what moves each criminal. Keep running the score engine in the background and log its values for comparison. | Must |
| FR-10 | Run the regex detectors and regex `_check_agreement` on every Claude transcript as a cross-check against the classifier and the tool-call outcome. | Should |
| FR-11 | Seed `random.choice` for the canned lines so E1 and E2 runs are reproducible. | Must |
| FR-12 | Log every run as JSONL: condition, config hash, personas, starting role, model, full transcript, tool calls and rejections, classifier outputs, state values per turn, tokens, latency, outcome. | Must |
| FR-13 | Use prompt caching on the static persona prompts and tool definitions. Check the current minimum cacheable prompt length first; if the persona prompts fall below it, document that caching did not apply. | Could |
| FR-14 | Package the LLM-judge rubric as an Agent Skill (`SKILL.md`, rubric, scoring script) that can score any negotiation transcript, and document how to load it. Check the current Skills docs for API usage. | Should |
| FR-15 | Stretch: a mediator agent, multi-demand scenarios (the report's future work), or tool calling for the Gemma baseline. | Could |

## Evaluation requirements

| ID | Metric | How it is measured | Applies to |
| --- | --- | --- | --- |
| EV-1 | Outcome distribution | % of runs ending in criminal release, FBI vehicle, or no concession, per persona pairing | All |
| EV-2 | 2×2 replication | Difference in release rate between FBI personas, for each criminal persona, with a 95% CI. Does the original pattern hold? | All |
| EV-3 | Rounds to outcome | Mean and spread of messages per run | All |
| EV-4 | Latency | Mean seconds per turn and per run, with hardware recorded (local vs API is not like-for-like) | All |
| EV-5 | Perplexity | GPT-2 on the full transcript with the original 512-token truncation, plus per speaker | All |
| EV-6 | Dialogue quality | LLM judge with a fixed 1–5 rubric: persona adherence, coherence, realism, strategic consistency | All |
| EV-7 | Rule violations and refusals | Refusals, character breaks or admitting to being an AI, FBI implying it can free hostages, vehicle offered without a threat, self-contradicting replies | All |
| EV-8 | Repetition rate | % of turns flagged by the original `_is_repetitive` logic (Jaccard > 0.6 against the last 3 replies) | All |
| EV-9 | Detector agreement | Cohen's kappa between regex detectors and the LLM classifier per tactic; agreement between regex `_check_agreement` and tool-call outcomes | Claude |
| EV-10 | Tool-call validity | % of tool calls passing validation first time | E3 to E5 |
| EV-11 | Cost | Input and output tokens and £ per run, including classifier and judge calls | Claude |

Experimental rules:

1. Rerun the Gemma baseline (E1) with the refactored code, so all numbers come from the same scenarios, turn limit and seeds.
2. Run every one of the 8 configurations at least 10 times per condition (80 runs per condition), and 20 times if the budget allows.
3. Use a judge model that is not an agent in the condition being scored (for example an Opus-tier model; check current model IDs). Validate it against 20 transcripts you score by hand, and require agreement within one point on at least 80% of them.
4. Report rates with Wilson 95% intervals and means with bootstrap 95% intervals.
5. Write down what you expect from E3, E4 and E5 before running them.
6. Report metrics that got worse, not just those that improved, and include the E4 result whichever way it goes.

## Non-functional requirements

| ID | Requirement |
| --- | --- |
| NF-1 | **Budget:** a configurable spend cap per experiment; the runner stops when estimated cost reaches it. |
| NF-2 | **Reliability:** retry rate-limit and server errors with exponential backoff; a failed run is logged, never silently dropped. |
| NF-3 | **Reproducibility:** one YAML config per condition fixes models, temperature, turn limit, seeds, run count and prompt versions; each results file records its config. |
| NF-4 | **Security:** API key read from an environment variable; `.env` in `.gitignore`; a `.env.example` in the repo. |
| NF-5 | **Testing:** unit tests for tool validation, rule-engine transitions and both memory modes, using a mocked client so tests cost nothing. |
| NF-6 | **Code quality:** type hints, a formatter (e.g. ruff), a `requirements.txt`, and one command to run an experiment. |

## Repo and documentation deliverables

The README is what a recruiter actually reads, so it leads with the result.

- [ ] Public GitHub repo, linked from the CV header, with the original code tagged `v0-university`
- [ ] README opening with the headline result in one sentence, then the results table (E1 to E5, all metrics)
- [ ] A "What the original code actually did" note summarising the baseline section above, including that the report's figures came from n = 3 and E1 replaces them
- [ ] The E4 finding stated plainly: whether the 2×2 pattern survived without hand-written rules
- [ ] Architecture diagram: personas, `LLMClient`, memory, classifier, rule engine, tools, evaluator
- [ ] Quick start: install, set API key, run one negotiation in one command
- [ ] "Design decisions" section: why tools, why the rule engine gates actions, why a separate classifier instead of self-reported tactics, how the judge was validated
- [ ] Prompt iteration log: each persona prompt change and its effect on the metrics
- [ ] Failure analysis with transcript excerpts
- [ ] "How I'd adapt this for a customer": for example, simulated difficult-customer personas for testing customer-service agents, or de-escalation training
- [ ] Two example transcripts (one release, one vehicle concession) in `examples/`, plus a two-minute screen recording of one run
- [ ] A note that the original was a University of Nottingham project, rebuilt independently in 2026, and that, as the report concludes, AI here is a training and research tool, not a replacement for human negotiators

## Milestones and acceptance criteria

Each milestone is done only when its acceptance check passes.

0. **Smoke test (E0).** Done when both criminal personas pass on Claude, or an adapted scenario is decided and recorded.
1. **Clean baseline.** Done when the original code is tagged, imports and requirements are fixed, the Gemma version runs through `LLMClient` with seeds and a 10-round limit, and E1 has 80 or more runs.
2. **Model swap (E2).** Done when the same logic runs on Claude Haiku in `last_message` mode and E2 has 80 or more runs.
3. **Tools and classifier (E3).** Done when tool calls drive outcomes, validation and memory-mode tests pass, and E3 has 80 or more runs.
4. **LLM-decided outcomes (E4) and tier comparison (E5).** Done when both conditions have 80 or more runs within budget.
5. **Evaluation.** Done when all EV metrics are computed for every condition and the judge passes its 20-transcript check.
6. **Repo and CV.** Done when the README, diagram and results table are public and the CV bullet quotes measured numbers.

## Budget sizing

At 80 runs per condition, E1 to E5 come to about 400 negotiations, plus E0. Each Claude run makes up to 10 agent calls, plus one classifier call per FBI turn in E3 and E5, plus one judge call per transcript. Estimate cost from current per-token pricing for each model, then set the run count (10 or 20 per configuration) and the NF-1 cap accordingly.

## Assumptions and open questions

- Which version of the code produced the report's figures? The zip has `n_trials = 1` and `max_rounds = 8`, but the report states n = 3 and 10 rounds.
- `prompts.py` only survives as a compiled file. Confirm that the persona prompts inside `agents.py` are the ones used in the reported runs.
- Does the persona gating (empathy only for the unstable criminal, logical threats only for the calculated one) match what you intended? E4 tests its effect either way.
- What is your total API budget? It sets the run count in milestones 1 to 4.

## Target CV bullet (fill in after milestone 6)

Rebuilt the simulator on the Claude API with tool-based actions and an LLM tactic classifier, lifting [metric] from [E1] to [E3] across 8 configurations, and tested whether the persona effect survives without hand-written rules ([E4 result])
