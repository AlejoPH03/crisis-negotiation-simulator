"""Characterization tests: pin v0 game-logic quirks recorded in docs/DECISIONS.md.

These document behaviour that is kept on purpose (E1 and E2 must match v0).
"""

import random

from scripted import ScriptedResponder

from src.agents import CriminalAgent, FBIAgent
from src.llm.mock import MockLLMClient
from src.simulate import GenerationSettings, run_negotiation

GEN = GenerationSettings(temperature=0.6, max_tokens=150)


def criminal(persona):
    return CriminalAgent(persona, MockLLMClient(lambda s, m: "x"), GEN, random.Random(0))


def test_detect_authority_is_never_called(monkeypatch):
    agent = criminal("criminal_unstable")
    called = []
    monkeypatch.setattr(agent, "_detect_authority", lambda m: called.append(m) or True)
    agent.respond("You must comply now. This is your last chance. You're facing life in prison.")
    assert called == []


def test_threat_and_escalation_share_patterns():
    agent = criminal("criminal_unstable")
    msg = "We will storm the building."
    assert agent._detect_threat(msg) and agent._detect_escalation(msg)
    agent.emotional_state["calmness"] = 0.9
    agent._update_emotional_state(msg)
    # -0.3 (threat) -0.2 (escalation) -0.01 (decay)
    assert round(agent.emotional_state["calmness"], 6) == 0.39


def test_logical_threats_match_almost_any_mention_of_time_or_situation():
    agent = criminal("criminal_calculated")
    assert agent._detect_logical_threats("Take your time.")
    assert agent._detect_logical_threats("Let's resolve the situation.")


def test_delay_messages_also_count_as_logical_threats():
    agent = criminal("criminal_calculated")
    msg = "We need to verify the details first."
    assert agent._detect_vehicle_delay(msg) and agent._detect_logical_threats(msg)
    before = dict(agent.strategic_state)
    agent._update_strategic_state(msg)
    # decay first (-0.01 coop), then +0.2 (logical) -0.2 (delay): net cooperation change -0.01
    assert round(agent.strategic_state["cooperation"], 6) == round(before["cooperation"] - 0.01, 6)


def test_empathy_regex_misses_contraction_from_fbi_prompt():
    """The empathy prompt says 'I understand you're scared'; the detector needs 'you are'."""
    agent = criminal("criminal_unstable")
    assert not agent._detect_empathy("I understand you're scared.")
    assert agent._detect_empathy("I understand you are scared.")


def test_empathy_and_authority_gated_to_unstable_logical_to_calculated():
    unstable, calculated = criminal("criminal_unstable"), criminal("criminal_calculated")
    assert not calculated._detect_empathy("I understand you are scared.")
    assert not unstable._detect_logical_threats("You're facing life in prison.")


def test_fbi_agreement_does_not_end_run_while_release_line_repeats():
    """FBI goes to AwaitAgreementState, not EndState; repeated release lines keep the run going."""
    script = {
        "fbi": ["I understand you are scared. Let's work together to make sure everyone is safe."],
        "criminal": ["Okay."],
    }
    result = run_negotiation(
        "fbi_empathy",
        "criminal_unstable",
        "fbi",
        10,
        llm=MockLLMClient(ScriptedResponder(script)),
        rng=random.Random(0),
        generation=GEN,
    )
    assert result["criminal_conceded"] == 1
    assert result["rounds_taken"] == 10
    thanks = [m for m in result["history"] if m["content"].startswith("Thank you for agreeing")]
    assert len(thanks) == 4


def test_fbi_canned_vehicle_line_unreachable():
    """get_acknowledgement_message (with the vehicle line) is only reached via BaseAgent.respond,
    which FBIAgent overrides, so the FBI never says the canned vehicle line."""
    fbi = FBIAgent("fbi_empathy", MockLLMClient(lambda s, m: "Stay calm."), GEN)
    reply = fbi.respond("I will hurt her if you don't hurry!")
    assert reply == "Stay calm."
