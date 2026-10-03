# Crisis Negotiation Simulator: Claude rebuild

Rebuild of a University of Nottingham COMP3004 project (Gemma 3 via Ollama) on the Claude API.

## Source of truth
- `docs/SPEC.md` is the spec. Requirement IDs (FR-x, EV-x, NF-x, E0 to E5) come from it.
- `PROGRESS.md` tracks milestone status. Read it at the start of every session and update it at the end.
- `docs/DECISIONS.md` records every decision where the spec was ambiguous or conflicted with the code.

## Working rules
- Work on one milestone at a time. Do not start the next one until its acceptance check passes and I approve.
- Write tests before implementation. A milestone is done only when its tests and its acceptance check pass.
- The original code is tagged `v0-university`. Never rewrite that history. Its behaviour must stay reproducible through config (condition E1).
- If the spec is unclear or conflicts with the code, stop and ask me. Do not guess.
- Reference requirement IDs in commit messages (e.g. `FR-6: validate tool calls`).

## Cost and safety
- Tests must use the mocked `LLMClient`. Never call the Anthropic API or Ollama from tests.
- Never start a paid experiment run without asking me first. Always respect the budget cap in the config.
- Read the API key from the `ANTHROPIC_API_KEY` environment variable. Never print, log or commit it.

## Results integrity
- Never invent, estimate, round or edit experimental results.
- Every number in the README must come from a file in `results/`, with the config that produced it.
- Report metrics that got worse, not only improvements.

## Environment
- Python 3.12, dependencies in `requirements.txt`
- Ollama running locally with `gemma3:4b` for the baseline
- Claude model IDs are set in config files, not in code

## Commands (fill in as they are created)
- Install: `pip install -r requirements.txt`
- Test: `pytest`
- Lint and format: `ruff check . && ruff format .`
- Run one negotiation: TBD
- Run an experiment: TBD
