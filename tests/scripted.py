"""Scripted LLM replies shared by the v0 and refactored runs."""

from __future__ import annotations

import copy
import random

from src.llm.mock import persona_from_system

# Lines chosen to hit the detectors, thresholds and FSM paths in agents.py.
FBI_POOL = [
    # empathy + de-escalation (unstable criminal calms down)
    "I understand you are scared. Let's work together to make sure everyone is safe.",
    "I hear your frustration. Let's talk this through together.",
    "I care about your safety and I want to help you get through this.",
    # logical threats / delays (calculated criminal)
    "You're facing life in prison. Legal consequences are severe.",
    "We need to verify the details first. The process takes time.",
    "Our tactical team is ready to breach. This is your last chance.",
    # threats / escalation
    "We will storm the building if you do not comply.",
    "We are not going to tolerate this any longer.",
    # vehicle agreement and non-agreement
    "I will provide you with an unmarked vehicle.",
    "We can't provide the vehicle yet. We need approval.",
    "I will provide you with an unmarked vehicle if you release the pregnant hostage.",
    "Let's discuss the vehicle once she is out.",
    # FBI quirk: its own reply matches the release regex
    "I will release the pregnant hostage.",
    # understanding question
    "Do you understand what I am asking?",
    # neutral
    "Talk to me. What do you need right now?",
    "",
]

CRIMINAL_POOL = [
    "I will release the pregnant hostage.",
    "Fine, I'll let her go.",
    "I will release her if you give me the car.",
    "I will release the pregnant hostage... once the vehicle is here.",
    "I will hurt her if you don't hurry.",
    "She is going to suffer if you keep stalling!",
    "Time is running out. Get me the car now.",
    "I need an unmarked vehicle out back.",
    "Don't push me.",
    "I'm warning you, this will end badly.",
    # criminal quirk: its own reply matches the vehicle regex
    "I will provide you with an unmarked vehicle.",
    "Okay.",
    "Do you understand me?",
    "",
]

# Hand-written scripts that force specific outcomes.
HAND_SCRIPTS = {
    "release": {
        "fbi": ["I understand you are scared. Let's work together to make sure everyone is safe."],
        "criminal": ["Okay."],
    },
    "vehicle": {
        "fbi": ["I will provide you with an unmarked vehicle."],
        "criminal": ["I will hurt her if you don't hurry."],
    },
    "no_concession": {
        "fbi": ["Talk to me. What do you need right now?"],
        "criminal": ["I need a car."],
    },
    "fbi_self_agreement": {
        "fbi": ["I will release the pregnant hostage."],
        "criminal": ["What?"],
    },
    "criminal_self_agreement": {
        "fbi": ["Talk to me."],
        "criminal": ["I will provide you with an unmarked vehicle."],
    },
}


def random_script(seed: int, length: int = 12) -> dict[str, list[str]]:
    rng = random.Random(f"script-{seed}")
    return {
        "fbi": [rng.choice(FBI_POOL) for _ in range(length)],
        "criminal": [rng.choice(CRIMINAL_POOL) for _ in range(length)],
    }


class ScriptedResponder:
    """Returns the next scripted line for the speaking role (from the system prompt)."""

    def __init__(self, script: dict[str, list[str]]):
        self.script = script
        self.counters = {"fbi": 0, "criminal": 0}

    def __call__(self, system: str, messages: list[dict[str, str]]) -> str:
        role = persona_from_system(system).split("_")[0]
        i = self.counters[role]
        self.counters[role] += 1
        lines = self.script[role]
        return lines[i % len(lines)]


class FakeOllamaChat:
    """Stands in for `ollama.chat`; records deep copies of every call."""

    def __init__(self, responder: ScriptedResponder):
        self.responder = responder
        self.calls: list[dict] = []

    def __call__(self, model, messages, options=None, **kwargs):
        self.calls.append(
            {"model": model, "messages": copy.deepcopy(messages), "options": copy.deepcopy(options), **kwargs}
        )
        assert messages[0]["role"] == "system"
        text = self.responder(messages[0]["content"], messages[1:])
        return {"message": {"role": "assistant", "content": text}, "prompt_eval_count": 11, "eval_count": 7}
