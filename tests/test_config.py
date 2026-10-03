import copy
from pathlib import Path

import pytest
import yaml

from src.config import ConfigError, config_hash, load_config, parse_config

CONFIGS = Path(__file__).parent.parent / "configs"


def raw(name="e1_gemma.yaml"):
    return yaml.safe_load((CONFIGS / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", ["e1_gemma.yaml"])
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


def test_hash_is_stable_and_order_independent():
    a = raw()
    b = dict(reversed(list(copy.deepcopy(a).items())))
    assert config_hash(a) == config_hash(b)
    c = copy.deepcopy(a)
    c["llm"]["temperature"] = 0.7
    assert config_hash(a) != config_hash(c)


def mutate(fn, name="e1_gemma.yaml"):
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
        lambda d: d["budget"].update(cap_usd=-1),
    ],
)
def test_invalid_configs_rejected(change):
    with pytest.raises(ConfigError):
        parse_config(mutate(change))
