"""Command line entry point. Run from the repo root:

python -m src negotiate  --config configs/e1_gemma.yaml
python -m src experiment --config configs/e2_haiku.yaml
python -m src smoke      --config configs/e0_smoke.yaml
python -m src analyze    results/e2/<timestamp> [more folders] [--by-start]
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import ExperimentConfig, load_config
from .runner import RunSpec, build_client, execute_runs, make_out_dir, run_experiment


def _setup_logging(verbose: bool) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, format="%(message)s", stream=sys.stdout)
    for noisy in ("httpx", "httpx2", "httpcore", "httpcore2", "anthropic"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _confirm_paid(config: ExperimentConfig, n_runs: int, models: list[str], args: argparse.Namespace) -> bool:
    """Paid runs need an explicit yes (CLAUDE.md: never start a paid run without asking)."""
    if args.dry_run or config.llm.backend != "claude" or args.yes:
        return True
    cap = f"${config.budget.cap_usd:.2f}" if config.budget.cap_usd is not None else "none"
    answer = input(f"About to start {n_runs} paid run(s) on {', '.join(models)} (budget cap {cap}). Continue? [y/N] ")
    return answer.strip().lower() in {"y", "yes"}


def _print_summary(result) -> None:
    s = result.summary
    print("\n=== Summary ===")
    print(f"Output:   {result.out_dir}")
    print(f"Runs:     {s['runs']} of {s['runs_planned']} planned  {s['counts']}")
    if s["stopped_reason"]:
        print(f"Stopped:  {s['stopped_reason']}")
    print(f"Tokens:   {s['tokens']}")
    cost = f"${s['cost_usd']:.4f}" if s["cost_usd"] is not None else "n/a (no prices for this model)"
    print(f"Cost:     {cost}")


def cmd_negotiate(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    spec = RunSpec(
        model=config.llm.model,
        fbi_persona=args.fbi or config.game.fbi_personas[0],
        criminal_persona=args.criminal or config.game.criminal_personas[0],
        starts_with=args.starts_with or config.game.starts_with[0],
        trial=1,
    )
    if args.no_perplexity or args.dry_run:
        config.run.compute_perplexity = False
    if not _confirm_paid(config, 1, [config.llm.model], args):
        print("Cancelled.")
        return 1
    print(f"{config.condition}: {spec.fbi_persona} vs {spec.criminal_persona}, {spec.starts_with} starts, {spec.model}")
    result = execute_runs(
        config,
        [spec],
        out_dir=make_out_dir(config, args.dry_run, label="negotiate"),
        client_factory=lambda model: build_client(config, model, args.dry_run),
        seed_override=args.seed,
    )
    rec = result.records[0]
    print(f"\nStatus:   {rec['status']}" + (f"  ({rec['error']['message']})" if rec["error"] else ""))
    if rec["outcome"]:
        print(f"Outcome:  {rec['outcome']['label']}  in {rec['rounds_taken']} messages")
        print(f"Perplexity: {rec['perplexity']}")
    _print_summary(result)
    return 0 if rec["status"] == "completed" else 2


def cmd_experiment(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    n_runs = (
        len(config.game.fbi_personas)
        * len(config.game.criminal_personas)
        * len(config.game.starts_with)
        * config.run.runs_per_configuration
    )
    if not _confirm_paid(config, n_runs, [config.llm.model], args):
        print("Cancelled.")
        return 1
    result = run_experiment(config, dry_run=args.dry_run)
    _print_summary(result)
    return 0 if result.stopped_reason is None else 2


def cmd_smoke(args: argparse.Namespace) -> int:
    from .smoke import run_smoke, smoke_grid

    config = load_config(args.config)
    if config.smoke is None:
        print(f"{args.config} has no smoke section.")
        return 1
    if not _confirm_paid(config, len(smoke_grid(config)), config.smoke.models, args):
        print("Cancelled.")
        return 1
    result = run_smoke(config, dry_run=args.dry_run)
    _print_summary(result)
    flagged = sum(1 for r in result.records if r["flags"])
    print(f"Flagged:  {flagged} of {len(result.records)} runs. Start with {result.out_dir / 'summary.md'}")
    return 0 if result.stopped_reason is None else 2


def cmd_analyze(args: argparse.Namespace) -> int:
    from .analyze import analyze_folder

    for folder in args.folders:
        if not (folder / "runs.jsonl").exists():
            print(f"{folder} has no runs.jsonl.")
            return 1
        print(analyze_folder(folder, by_start=args.by_start))
        print(f"Written: {folder / 'analysis.md'} and {folder / 'analysis.json'}", end="\n\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m src", description="Crisis negotiation simulator")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--config", type=Path, required=True, help="YAML config for one condition")
        p.add_argument("--dry-run", action="store_true", help="use a canned mock client: no Ollama, no API calls")
        p.add_argument("--yes", action="store_true", help="skip the confirmation for paid runs")
        p.add_argument("--verbose", action="store_true", help="also log detector hits and state updates")

    p = sub.add_parser("negotiate", help="run one negotiation")
    common(p)
    p.add_argument("--fbi", choices=["fbi_empathy", "fbi_authority"])
    p.add_argument("--criminal", choices=["criminal_unstable", "criminal_calculated"])
    p.add_argument("--starts-with", choices=["fbi", "criminal"])
    p.add_argument("--seed", type=int, help="canned-line seed (default: run.seed from the config)")
    p.add_argument("--no-perplexity", action="store_true", help="skip GPT-2 perplexity")
    p.set_defaults(func=cmd_negotiate)

    p = sub.add_parser("experiment", help="run the full 2x2x2 grid from the config")
    common(p)
    p.set_defaults(func=cmd_experiment)

    p = sub.add_parser("smoke", help="E0: every persona pairing on every model in smoke.models, with flags")
    common(p)
    p.set_defaults(func=cmd_smoke)

    p = sub.add_parser("analyze", help="per-pairing metrics for results folders (no backend calls)")
    p.add_argument("folders", type=Path, nargs="+", help="results folder(s) containing runs.jsonl")
    p.add_argument("--by-start", action="store_true", help="split each pairing by starting role")
    p.set_defaults(func=cmd_analyze, verbose=False)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _setup_logging(args.verbose)
    try:
        from dotenv import load_dotenv

        load_dotenv(override=False)  # only fills environment variables (NF-4)
    except ImportError:
        pass
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
