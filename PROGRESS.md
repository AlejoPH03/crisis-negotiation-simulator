# Progress

Milestones from `docs/SPEC.md`. A milestone is done only when its tests **and** its acceptance check pass.

| # | Milestone | Status | Acceptance check |
| --- | --- | --- | --- |
| 0 | Smoke test (E0) | Code complete, mocked tests pass. **Awaiting live run and owner review.** | Both criminal personas pass on Claude, or an adapted scenario is decided and recorded |
| 1 | Clean baseline (E1) | Code complete, mocked tests and equivalence test pass. **Awaiting live E1 run.** | Original tagged ✅, imports and requirements fixed ✅, Gemma runs through `LLMClient` with seeds and a 10-round limit ✅ (mocked), E1 has ≥ 80 runs ⏳ |
| 2 | Model swap (E2) | Code complete, mocked tests pass. **Awaiting live E2 run.** | Same logic on Claude Haiku in `last_message` mode ✅ (mocked), E2 has ≥ 80 runs ⏳ |
| 3 | Tools and classifier (E3) | Not started | |
| 4 | LLM-decided outcomes (E4) and tier comparison (E5) | Not started | |
| 5 | Evaluation | Not started | |
| 6 | Repo and CV | Not started | |

## Log

- **2026-10-03.** Milestones 0–2 implemented and verified with mocks only (no Ollama or Anthropic calls). Decisions D1–D20 are in `docs/DECISIONS.md`. Next: the owner runs E0, E1 and E2 live, then reviews the E0 flags.
