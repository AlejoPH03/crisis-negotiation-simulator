"""Experiment runner: grid of runs, JSONL logging, failures, budget (FR-11, FR-12, NF-1, NF-2, NF-3)."""

from __future__ import annotations

import json
import logging
import os
import platform
import random
import sys
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from .budget import BudgetedClient, BudgetExceeded, BudgetTracker
from .config import ExperimentConfig
from .llm.base import LLMClient, LLMError
from .simulate import run_negotiation

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
STATUSES = ("completed", "failed", "aborted_budget")


class _Default:
    pass


DEFAULT = _Default()
PerplexityFn = Callable[[str], float]


@dataclass(frozen=True)
class RunSpec:
    model: str
    fbi_persona: str
    criminal_persona: str
    starts_with: str
    trial: int


@dataclass
class ExperimentResult:
    out_dir: Path
    records: list[dict[str, Any]] = field(default_factory=list)
    stopped_reason: str | None = None
    summary: dict[str, Any] = field(default_factory=dict)


def build_client(config: ExperimentConfig, model: str, dry_run: bool = False) -> LLMClient:
    if dry_run:
        from .llm.mock import dry_run_client

        return dry_run_client(model)
    if config.llm.backend == "ollama":
        from .llm.ollama_client import OllamaClient

        return OllamaClient(model, config.llm.backend_options, config.retry)
    from .llm.claude_client import ClaudeClient

    return ClaudeClient(model, config.llm.opening_user_message, config.retry)


def environment_info() -> dict[str, Any]:
    """Hardware notes for EV-4 (local and API latency are not like-for-like)."""
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "python": sys.version.split()[0],
    }


def outcome_label(criminal_conceded: int, fbi_conceded: int) -> str:
    if criminal_conceded and fbi_conceded:
        return "both"
    if criminal_conceded:
        return "criminal_release"
    if fbi_conceded:
        return "fbi_vehicle"
    return "none"


def experiment_grid(config: ExperimentConfig) -> list[RunSpec]:
    """Same order as v0 run_experiments: fbi, criminal, starts_with, trial."""
    return [
        RunSpec(config.llm.model, fbi, crim, starts, trial)
        for fbi in config.game.fbi_personas
        for crim in config.game.criminal_personas
        for starts in config.game.starts_with
        for trial in range(1, config.run.runs_per_configuration + 1)
    ]


def _resolve_perplexity(config: ExperimentConfig, perplexity_fn: Any) -> PerplexityFn | None:
    if not config.run.compute_perplexity or perplexity_fn is None:
        return None
    if isinstance(perplexity_fn, _Default):
        from .metrics import compute_perplexity

        return compute_perplexity
    return perplexity_fn


def run_single(
    config: ExperimentConfig,
    llm: LLMClient,
    tracker: BudgetTracker,
    spec: RunSpec,
    *,
    run_index: int,
    seed: int,
    perplexity_fn: PerplexityFn | None,
) -> dict[str, Any]:
    trace: list[dict[str, Any]] = []
    error = None
    result = None
    start = time.perf_counter()
    try:
        result = run_negotiation(
            spec.fbi_persona,
            spec.criminal_persona,
            spec.starts_with,
            config.game.max_rounds,
            llm=llm,
            rng=random.Random(seed),
            generation=config.llm.generation,
            trace=trace,
        )
        status = "completed"
    except LLMError as e:
        status = "failed"
        error = {"type": "LLMError", "message": str(e), "retryable": e.retryable, "attempts": e.attempts}
        logger.error("Run %d failed: %s", run_index, e)
    except BudgetExceeded as e:
        status = "aborted_budget"
        error = {"type": "BudgetExceeded", "message": str(e), "retryable": False, "attempts": 0}
        logger.warning("Run %d aborted: %s", run_index, e)
    elapsed = time.perf_counter() - start

    llm_calls = [{"turn": t["turn"], "speaker": t["speaker"], **c} for t in trace for c in t["llm_calls"]]
    costs = [tracker.cost(c["model"], c["input_tokens"], c["output_tokens"]) for c in llm_calls]
    priced = [c for c in costs if c is not None]
    # A priced model with no completed calls cost $0; only an unpriced model's cost is unknown.
    model_priced = llm.model in tracker.pricing

    perplexity = perplexity_error = None
    if result is not None and perplexity_fn is not None:
        try:
            perplexity = perplexity_fn(result["transcript"])
        except Exception as e:  # recorded, not hidden; the run itself completed
            perplexity_error = f"{type(e).__name__}: {e}"
            logger.warning("Perplexity failed for run %d: %s", run_index, perplexity_error)

    outcome = None
    if result is not None:
        outcome = {
            "criminal_conceded": result["criminal_conceded"],
            "fbi_conceded": result["fbi_conceded"],
            "label": outcome_label(result["criminal_conceded"], result["fbi_conceded"]),
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "condition": config.condition,
        "config_hash": config.hash,
        "config": config.raw,
        "run_index": run_index,
        "trial": spec.trial,
        "seed": seed,
        "fbi_persona": spec.fbi_persona,
        "criminal_persona": spec.criminal_persona,
        "starts_with": spec.starts_with,
        "backend": config.llm.backend,
        "model": llm.model,
        "status": status,
        "error": error,
        "transcript": trace,
        "llm_calls": llm_calls,
        "outcome": outcome,
        "rounds_taken": len(trace),
        "perplexity": perplexity,
        "perplexity_error": perplexity_error,
        "execution_time_s": result["execution_time"] if result is not None else elapsed,
        "tokens": {
            "input": sum(c["input_tokens"] or 0 for c in llm_calls),
            "output": sum(c["output_tokens"] or 0 for c in llm_calls),
        },
        "cost_usd": sum(priced) if (priced or model_priced) else None,
        "environment": environment_info(),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }


def summarize(config: ExperimentConfig, records: list[dict[str, Any]], stopped_reason: str | None) -> dict[str, Any]:
    """Aggregate counts only, computed from the records (no estimates)."""
    counts = Counter(r["status"] for r in records)
    by_config: dict[str, Counter] = {}
    for r in records:
        key = "|".join([r["model"], r["fbi_persona"], r["criminal_persona"], r["starts_with"]])
        c = by_config.setdefault(key, Counter())
        c[r["status"]] += 1
        if r["outcome"]:
            c[r["outcome"]["label"]] += 1
    costs = [r["cost_usd"] for r in records if r["cost_usd"] is not None]
    return {
        "condition": config.condition,
        "config_hash": config.hash,
        "runs": len(records),
        "counts": {s: counts.get(s, 0) for s in STATUSES},
        "stopped_reason": stopped_reason,
        "by_configuration": {k: dict(v) for k, v in by_config.items()},
        "tokens": {
            "input": sum(r["tokens"]["input"] for r in records),
            "output": sum(r["tokens"]["output"] for r in records),
        },
        "cost_usd": sum(costs) if costs else None,
        "llm_stop_reasons": dict(Counter(c["stop_reason"] for r in records for c in r["llm_calls"])),
    }


def make_out_dir(config: ExperimentConfig, dry_run: bool, label: str = "") -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    name = "-".join(p for p in ("dry-run" if dry_run else "", label, stamp) if p)
    return Path(config.run.output_dir) / name


def execute_runs(
    config: ExperimentConfig,
    specs: list[RunSpec],
    *,
    out_dir: Path,
    client_factory: Callable[[str], LLMClient],
    perplexity_fn: Any = DEFAULT,
    seed_override: int | None = None,
    annotate: Callable[[dict[str, Any]], None] | None = None,
) -> ExperimentResult:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "config.yaml").write_text(yaml.safe_dump(config.raw, sort_keys=False), encoding="utf-8")
    ppl = _resolve_perplexity(config, perplexity_fn)
    tracker = BudgetTracker(config.budget.cap_usd, config.budget.pricing)
    clients: dict[str, LLMClient] = {}
    result = ExperimentResult(out_dir=out_dir)
    consecutive_failures = 0
    base_seed = config.run.seed if seed_override is None else seed_override

    with open(out_dir / "runs.jsonl", "w", encoding="utf-8") as jsonl:
        for run_index, spec in enumerate(specs):
            if tracker.exhausted:
                result.stopped_reason = "budget_cap"
                break
            if spec.model not in clients:
                clients[spec.model] = BudgetedClient(client_factory(spec.model), tracker)
            record = run_single(
                config,
                clients[spec.model],
                tracker,
                spec,
                run_index=run_index,
                seed=base_seed + run_index,
                perplexity_fn=ppl,
            )
            if annotate is not None:
                annotate(record)
            jsonl.write(json.dumps(record, ensure_ascii=False) + "\n")
            jsonl.flush()
            result.records.append(record)
            logger.info(
                "[%d/%d] %s %s vs %s (%s starts) trial %d: %s, %s, %d msgs, cost %s",
                run_index + 1,
                len(specs),
                record["model"],
                spec.fbi_persona,
                spec.criminal_persona,
                spec.starts_with,
                spec.trial,
                record["status"],
                record["outcome"]["label"] if record["outcome"] else "-",
                record["rounds_taken"],
                f"${record['cost_usd']:.4f}" if record["cost_usd"] is not None else "n/a",
            )
            if record["status"] == "aborted_budget":
                result.stopped_reason = "budget_cap"
                break
            consecutive_failures = consecutive_failures + 1 if record["status"] == "failed" else 0
            if consecutive_failures >= config.run.max_consecutive_failures:
                result.stopped_reason = "max_consecutive_failures"
                logger.error("Stopping: %d consecutive failed runs", consecutive_failures)
                break

    result.summary = summarize(config, result.records, result.stopped_reason)
    result.summary["runs_planned"] = len(specs)
    (out_dir / "summary.json").write_text(json.dumps(result.summary, indent=2), encoding="utf-8")
    return result


def run_experiment(
    config: ExperimentConfig,
    *,
    client_factory: Callable[[str], LLMClient] | None = None,
    out_dir: str | Path | None = None,
    perplexity_fn: Any = DEFAULT,
    dry_run: bool = False,
) -> ExperimentResult:
    """Run the full 2x2x2 grid, runs_per_configuration times each.

    A dry run uses canned mock replies and skips perplexity (no GPT-2 download).
    """
    factory = client_factory or (lambda model: build_client(config, model, dry_run))
    return execute_runs(
        config,
        experiment_grid(config),
        out_dir=Path(out_dir) if out_dir is not None else make_out_dir(config, dry_run),
        client_factory=factory,
        perplexity_fn=None if dry_run else perplexity_fn,
    )
