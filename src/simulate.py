"""
Single negotiation between an FBI agent and a criminal agent.

The turn loop is unchanged from v0-university. Differences: the LLM client,
generation settings and canned-line RNG are passed in (FR-1, FR-11), the
per-turn trace is recorded for JSONL logging (FR-12), and perplexity is
computed by the runner instead of here.
"""

import logging
import random
from typing import Any

from .agents import BaseAgent, CriminalAgent, FBIAgent
from .llm.base import GenerationSettings, LLMClient, LLMResponse
from .utils import timer

__all__ = ["GenerationSettings", "run_negotiation"]

logger = logging.getLogger(__name__)


def _call_record(response: LLMResponse) -> dict[str, Any]:
    return {
        "model": response.model,
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "latency_s": response.latency_s,
        "stop_reason": response.stop_reason,
        "attempts": response.attempts,
    }


def _criminal_state(agent: CriminalAgent) -> dict[str, float]:
    state = getattr(agent, "emotional_state", None) or getattr(agent, "strategic_state", None) or {}
    return dict(state)


def _turn_record(
    turn: int,
    label: str,
    agent: BaseAgent,
    response: str,
    calls_before: int,
    fbi_agent: FBIAgent,
    criminal_agent: CriminalAgent,
) -> dict[str, Any]:
    new_calls = agent.llm_calls[calls_before:]
    return {
        "turn": turn,
        "speaker": label,
        "persona": agent.persona,
        "content": response,
        # Raw LLM text for this turn; None when the reply was fully canned.
        "llm_text": new_calls[-1].text if new_calls else None,
        "canned_prefix": agent.last_canned_prefix if new_calls else None,
        "fbi_fsm_state": type(fbi_agent.current_state).__name__,
        "criminal_fsm_state": type(criminal_agent.current_state).__name__,
        "criminal_state": _criminal_state(criminal_agent),
        "llm_calls": [_call_record(r) for r in new_calls],
    }


@timer
def run_negotiation(
    fbi_persona: str,
    criminal_persona: str,
    starts_with: str = "fbi",
    max_rounds: int = 10,
    *,
    llm: LLMClient,
    rng: random.Random,
    generation: GenerationSettings,
    trace: list[dict[str, Any]] | None = None,
) -> dict:
    """
    Run a single negotiation simulation between FBI and criminal personas.

    Args:
        fbi_persona: "fbi_empathy" or "fbi_authority"
        criminal_persona: "criminal_unstable" or "criminal_calculated"
        starts_with: Which role starts the conversation ("fbi" or "criminal")
        max_rounds: Maximum number of messages (both agents together)
        llm: LLM client shared by both agents
        rng: RNG for the canned lines (seeded per run)
        generation: temperature and max_tokens
        trace: if given, one record per turn is appended as the run goes, so
            a failed run keeps its partial transcript

    Returns:
        Dict containing negotiation results
    """
    if trace is None:
        trace = []

    # Initialize agents
    fbi_agent = FBIAgent(fbi_persona, llm, generation, rng)
    criminal_agent = CriminalAgent(criminal_persona, llm, generation, rng)

    # Initialize turn order based on who starts
    if starts_with == "fbi":
        turn_order = [("fbi", fbi_agent), ("criminal", criminal_agent)]
    else:
        turn_order = [("criminal", criminal_agent), ("fbi", fbi_agent)]

    # Initialize history and tracking
    history = []
    prev_reply = None
    rounds = 0

    # Run conversation until either agent is finished or max rounds reached
    while not fbi_agent.is_finished() and not criminal_agent.is_finished() and rounds < max_rounds:
        # Get current speaker and agent based on who starts
        current_turn = rounds % len(turn_order)
        label, agent = turn_order[current_turn]

        # Get response from appropriate agent
        calls_before = len(agent.llm_calls)
        response = agent.respond(prev_reply)

        logger.info("[%s]: %s", label.upper(), response)
        trace.append(_turn_record(rounds + 1, label, agent, response, calls_before, fbi_agent, criminal_agent))

        # Add to history
        history.append({"role": label, "content": response})
        prev_reply = response
        rounds += 1

        # Check if we should end immediately after agreement
        if agent.is_finished():
            break

    # Calculate results
    criminal_concessions = len(fbi_agent.agreed_demands)
    fbi_concessions = len(criminal_agent.agreed_demands)
    transcript = "\n".join(msg["content"] for msg in history)

    return {
        "criminal_conceded": criminal_concessions,
        "fbi_conceded": fbi_concessions,
        "history": history,
        "transcript": transcript,
        "rounds_taken": len(history),
        "trace": trace,
    }
