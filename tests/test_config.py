import copy
from pathlib import Path

import pytest
import yaml

from src.config import ConfigError, config_hash, load_config, parse_config

CONFIGS = Path(__file__).parent.parent / "configs"


def raw(name="e2_haiku.yaml"):
    return yaml.safe_load((CONFIGS / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", ["e0_smoke.yaml", "e1_gemma.yaml", "e2_haiku.yaml", "e2_sonnet.yaml"])
def test_shipped_configs_load(name):
    cfg = load_config(CONFIGS / name)
    assert cfg.llm.temperature == 0.6  # FR-8
    assert cfg.game.max_rounds == 10  # FR-8
    assert cfg.game.memory_mode == "last_message"
    assert len(cfg.hash) == 64


def test_e1_reproduces_v0_settings():
    cfg = load_config(CONFIGS / "e1_gemma.yaml")
    assert (cfg.llm.backend, cfg.llm.model, cfg.llm.max_tokens) == ("ollama", "gemma3:4b", 150)
    assert cfg.llm.backend_options == {"top_k": 50, "top_p": 0.95, "frequency_penalty": 0.6, "presence_penalty": 0.6}
    assert cfg.run.runs_per_configuration == 10


def test_e2_settings():
    cfg = load_config(CONFIGS / "e2_haiku.yaml")
    assert (cfg.llm.backend, cfg.llm.model, cfg.llm.max_tokens) == ("claude", "claude-haiku-4-5", 300)
    assert cfg.budget.cap_usd == 5.0
    assert cfg.budget.pricing["claude-haiku-4-5"].output_per_mtok == 5.0
    assert cfg.llm.opening_user_message


def test_e0_settings():
    cfg = load_config(CONFIGS / "e0_smoke.yaml")
    assert cfg.smoke.models == ["claude-haiku-4-5", "claude-sonnet-4-6"]
    assert cfg.run.runs_per_configuration == 5


def test_hash_is_stable_and_order_independent():
    a = raw()
    b = dict(reversed(list(copy.deepcopy(a).items())))
    assert config_hash(a) == config_hash(b)
    c = copy.deepcopy(a)
    c["llm"]["temperature"] = 0.7
    assert config_hash(a) != config_hash(c)


def mutate(fn, name="e2_haiku.yaml"):
    data = raw(name)
    fn(data)
    return data


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d.update(extra_key=1),
        lambda d: d["llm"].update(top_p=0.9),
        lambda d: d["llm"].pop("model"),
        lambda d: d.pop("run"),
        lambda d: d["llm"].update(backend="openai"),
        lambda d: d["game"].update(memory_mode="full_history"),
        lambda d: d["game"].update(detection_mode="classifier"),
        lambda d: d["game"].update(decision_mode="tools"),
        lambda d: d["game"].update(fbi_personas=["fbi_friendly"]),
        lambda d: d["game"].update(starts_with=["hostage"]),
        lambda d: d["game"].update(max_rounds=0),
        lambda d: d["llm"].update(opening_user_message=None),
        lambda d: d["budget"].update(pricing={}),  # claude model without a price
        lambda d: d["budget"].update(cap_usd=-1),
    ],
)
def test_invalid_configs_rejected(change):
    with pytest.raises(ConfigError):
        parse_config(mutate(change))


def test_smoke_models_need_prices():
    data = mutate(lambda d: d["budget"]["pricing"].pop("claude-sonnet-4-6"), "e0_smoke.yaml")
    with pytest.raises(ConfigError):
        parse_config(data)


def test_e2_sonnet_differs_from_e2_haiku_only_in_model_price_output_and_cap():
    haiku, sonnet = raw("e2_haiku.yaml"), raw("e2_sonnet.yaml")
    assert sonnet["llm"]["model"] == "claude-sonnet-4-6"
    assert sonnet["run"]["output_dir"] == "results/e2_sonnet"
    assert sonnet["budget"] == {
        "cap_usd": 6.0,
        "pricing": {"claude-sonnet-4-6": {"input_per_mtok": 3.0, "output_per_mtok": 15.0}},
    }
    for section in (sonnet, haiku):
        section["llm"].pop("model")
        section["run"].pop("output_dir")
        section.pop("budget")
    assert sonnet == haiku
    assert load_config(CONFIGS / "e2_sonnet.yaml").llm.temperature == 0.6
