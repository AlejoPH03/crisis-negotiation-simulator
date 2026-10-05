# Progress

Milestones from `docs/SPEC.md`. A milestone is done only when its tests **and** its acceptance check pass.

| # | Milestone | Status | Acceptance check |
| --- | --- | --- | --- |
| 0 | Smoke test (E0) | Live run done (`results/e0/20261003-172725`). Owner verdict: `claude-haiku-4-5` fails, `claude-sonnet-4-6` passes (D24). | Both criminal personas pass on Claude ✅ (Sonnet 4.6) |
| 1 | Clean baseline (E1) | Live E1 run done: 80/80 completed (`results/e1/20261004-005801`). **Awaiting owner approval.** | Original tagged ✅, imports and requirements fixed ✅, Gemma runs through `LLMClient` with seeds and a 10-round limit ✅, E1 has ≥ 80 runs ✅ |
| 2 | Model swap (E2) | E2 on Haiku: 80/80 completed (`results/e2/20261004-235415`), kept as a negative result (D24). **Awaiting the live E2 run on Sonnet 4.6** (`configs/e2_sonnet.yaml`). | Same logic on Claude in `last_message` mode ✅, E2 (Sonnet) has ≥ 80 runs ⏳. ✱ The spec says Haiku; the owner switched to Sonnet (D24). |
| 3 | Tools and classifier (E3) | Not started | |
| 4 | LLM-decided outcomes (E4) and tier comparison (E5) | Not started | |
| 5 | Evaluation | Not started | |
| 6 | Repo and CV | Not started | |

## Log

- **2026-10-03.** Milestones 0–2 implemented and verified with mocks only (no Ollama or Anthropic calls). Decisions D1–D20 are in `docs/DECISIONS.md`. Next: the owner runs E0, E1 and E2 live, then reviews the E0 flags.
- **2026-10-03.** The first live E2 attempt failed: `anthropic` 1.x removed the `temperature` keyword. Fixed by sending temperature through `extra_body` (D21). The fake SDK now enforces the real signature, and a misleading cost message was fixed (D22). E2 needs to be rerun.
- **2026-10-03.** Clients now wrap only SDK, HTTP and connection errors; programming errors raise (D23).
- **2026-10-05.** E0 verdict recorded: Haiku fails, Sonnet 4.6 passes (D24). Added `configs/e2_sonnet.yaml` ($6 cap) and the results analysis script (D25). Open question: which model E3 and E4 use, and what E5 means now that E2 is on Sonnet.
