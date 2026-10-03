"""One YAML config per condition (FR-2, NF-3)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .budget import Price
from .llm.base import GenerationSettings
from .llm.retry import RetryPolicy

BACKENDS = {"ollama", "claude"}
FBI_PERSONAS = {"fbi_empathy", "fbi_authority"}
CRIMINAL_PERSONAS = {"criminal_unstable", "criminal_calculated"}
STARTERS = {"fbi", "criminal"}
# Only the original modes exist until E3.
MEMORY_MODES = {"last_message"}
DETECTION_MODES = {"regex"}
DECISION_MODES = {"rules"}


class ConfigError(ValueError):
    pass


@dataclass
class LLMSettings:
    backend: str
    model: str
    temperature: float
    max_tokens: int
    backend_options: dict[str, Any]
    opening_user_message: str | None

    @property
    def generation(self) -> GenerationSettings:
        return GenerationSettings(temperature=self.temperature, max_tokens=self.max_tokens)


@dataclass
class GameSettings:
    memory_mode: str
    detection_mode: str
    decision_mode: str
    max_rounds: int
    fbi_personas: list[str]
    criminal_personas: list[str]
    starts_with: list[str]


@dataclass
class RunSettings:
    runs_per_configuration: int
    seed: int
    output_dir: str
    compute_perplexity: bool
    max_consecutive_failures: int


@dataclass
class BudgetSettings:
    cap_usd: float | None
    pricing: dict[str, Price]


@dataclass
class SmokeSettings:
    models: list[str]
    starts_with_cycle: list[str]


@dataclass
class ExperimentConfig:
    condition: str
    description: str
    llm: LLMSettings
    game: GameSettings
    run: RunSettings
    retry: RetryPolicy
    budget: BudgetSettings
    smoke: SmokeSettings | None
    raw: dict[str, Any]
    hash: str


def config_hash(raw: dict[str, Any]) -> str:
    """SHA-256 of the canonical JSON form; key order does not matter."""
    return hashlib.sha256(json.dumps(raw, sort_keys=True).encode("utf-8")).hexdigest()


def _section(raw: dict[str, Any], name: str, keys: set[str], optional: set[str] = frozenset()) -> dict[str, Any]:
    data = raw.get(name)
    if not isinstance(data, dict):
        raise ConfigError(f"Missing or invalid section: {name}")
    unknown = set(data) - keys - optional
    missing = keys - set(data)
    if unknown:
        raise ConfigError(f"Unknown keys in {name}: {sorted(unknown)}")
    if missing:
        raise ConfigError(f"Missing keys in {name}: {sorted(missing)}")
    return data


def _choice(value: Any, allowed: set[str], what: str) -> str:
    if value not in allowed:
        raise ConfigError(f"{what} must be one of {sorted(allowed)}, got {value!r}")
    return value


def _choices(values: Any, allowed: set[str], what: str) -> list[str]:
    if not isinstance(values, list) or not values:
        raise ConfigError(f"{what} must be a non-empty list")
    return [_choice(v, allowed, what) for v in values]


def _positive_int(value: Any, what: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ConfigError(f"{what} must be a positive integer, got {value!r}")
    return value


def parse_config(raw: dict[str, Any]) -> ExperimentConfig:
    top = {"condition", "description", "llm", "game", "run", "retry", "budget"}
    unknown = set(raw) - top - {"smoke"}
    missing = top - set(raw)
    if unknown:
        raise ConfigError(f"Unknown top-level keys: {sorted(unknown)}")
    if missing:
        raise ConfigError(f"Missing top-level keys: {sorted(missing)}")

    llm_raw = _section(
        raw,
        "llm",
        {"backend", "model", "temperature", "max_tokens", "backend_options", "opening_user_message"},
    )
    llm = LLMSettings(
        backend=_choice(llm_raw["backend"], BACKENDS, "llm.backend"),
        model=str(llm_raw["model"]),
        temperature=float(llm_raw["temperature"]),
        max_tokens=_positive_int(llm_raw["max_tokens"], "llm.max_tokens"),
        backend_options=dict(llm_raw["backend_options"] or {}),
        opening_user_message=llm_raw["opening_user_message"],
    )
    if llm.backend == "claude":
        if not llm.opening_user_message:
            raise ConfigError("llm.opening_user_message is required for the claude backend")
        if llm.backend_options:
            raise ConfigError("llm.backend_options are not supported for the claude backend")

    game_raw = _section(
        raw,
        "game",
        {
            "memory_mode",
            "detection_mode",
            "decision_mode",
            "max_rounds",
            "fbi_personas",
            "criminal_personas",
            "starts_with",
        },
    )
    game = GameSettings(
        memory_mode=_choice(game_raw["memory_mode"], MEMORY_MODES, "game.memory_mode (others arrive in E3)"),
        detection_mode=_choice(game_raw["detection_mode"], DETECTION_MODES, "game.detection_mode"),
        decision_mode=_choice(game_raw["decision_mode"], DECISION_MODES, "game.decision_mode"),
        max_rounds=_positive_int(game_raw["max_rounds"], "game.max_rounds"),
        fbi_personas=_choices(game_raw["fbi_personas"], FBI_PERSONAS, "game.fbi_personas"),
        criminal_personas=_choices(game_raw["criminal_personas"], CRIMINAL_PERSONAS, "game.criminal_personas"),
        starts_with=_choices(game_raw["starts_with"], STARTERS, "game.starts_with"),
    )

    run_raw = _section(
        raw,
        "run",
        {"runs_per_configuration", "seed", "output_dir", "compute_perplexity", "max_consecutive_failures"},
    )
    if not isinstance(run_raw["seed"], int):
        raise ConfigError("run.seed must be an integer")
    run = RunSettings(
        runs_per_configuration=_positive_int(run_raw["runs_per_configuration"], "run.runs_per_configuration"),
        seed=run_raw["seed"],
        output_dir=str(run_raw["output_dir"]),
        compute_perplexity=bool(run_raw["compute_perplexity"]),
        max_consecutive_failures=_positive_int(run_raw["max_consecutive_failures"], "run.max_consecutive_failures"),
    )

    retry_raw = _section(raw, "retry", {"max_retries", "base_delay_s", "max_delay_s"})
    retry = RetryPolicy(
        max_retries=int(retry_raw["max_retries"]),
        base_delay_s=float(retry_raw["base_delay_s"]),
        max_delay_s=float(retry_raw["max_delay_s"]),
    )

    budget_raw = _section(raw, "budget", {"cap_usd", "pricing"})
    cap = budget_raw["cap_usd"]
    if cap is not None and (not isinstance(cap, (int, float)) or cap <= 0):
        raise ConfigError("budget.cap_usd must be null or a positive number")
    pricing = {}
    for model, price in (budget_raw["pricing"] or {}).items():
        if not isinstance(price, dict) or set(price) != {"input_per_mtok", "output_per_mtok"}:
            raise ConfigError(f"budget.pricing.{model} needs input_per_mtok and output_per_mtok")
        pricing[model] = Price(float(price["input_per_mtok"]), float(price["output_per_mtok"]))
    budget = BudgetSettings(cap_usd=float(cap) if cap is not None else None, pricing=pricing)

    smoke = None
    if "smoke" in raw:
        smoke_raw = _section(raw, "smoke", {"models", "starts_with_cycle"})
        if not isinstance(smoke_raw["models"], list) or not smoke_raw["models"]:
            raise ConfigError("smoke.models must be a non-empty list")
        smoke = SmokeSettings(
            models=[str(m) for m in smoke_raw["models"]],
            starts_with_cycle=_choices(smoke_raw["starts_with_cycle"], STARTERS, "smoke.starts_with_cycle"),
        )

    # Every paid model needs a price, so the budget cap can be enforced (NF-1).
    if llm.backend == "claude":
        models = {llm.model, *(smoke.models if smoke else [])}
        unpriced = sorted(m for m in models if m not in pricing)
        if unpriced:
            raise ConfigError(f"budget.pricing has no price for: {unpriced}")

    return ExperimentConfig(
        condition=str(raw["condition"]),
        description=str(raw["description"]),
        llm=llm,
        game=game,
        run=run,
        retry=retry,
        budget=budget,
        smoke=smoke,
        raw=raw,
        hash=config_hash(raw),
    )


def load_config(path: str | Path) -> ExperimentConfig:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if not isinstance(raw, dict):
        raise ConfigError(f"{path} is not a YAML mapping")
    return parse_config(raw)
