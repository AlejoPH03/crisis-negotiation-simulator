"""
Utility functions for the negotiation simulation.
"""

import time
from functools import wraps


def timer(func):
    """Decorator to measure function execution time."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        # Store execution time in the result dictionary if it's a dict
        if isinstance(result, dict):
            result["execution_time"] = execution_time
        return result

    return wrapper


def detect_agreement(agent, message: str | None) -> bool:
    """
    Check if a message indicates agreement to the current demand.

    Args:
        agent: The agent to check agreement for
        message: The message to check

    Returns:
        bool: True if the message indicates agreement
    """
    if not message:
        return False
    return agent._check_agreement(message)


def detect_timeout(agent) -> bool:
    """
    Check if the agent has been stuck on the same demand for too long.

    Args:
        agent: The agent to check timeout for

    Returns:
        bool: True if the agent should move to the next demand
    """
    return (
        agent.conversation_turns - agent.last_demand_attempt > 3 and agent.current_demand_idx < len(agent.demands) - 1
    )


def is_negotiation_complete(agent) -> bool:
    """
    Check if the agent has completed all its demands.

    Args:
        agent: The agent to check completion for

    Returns:
        bool: True if all demands have been agreed to
    """
    return agent.current_demand_idx >= len(agent.demands)
