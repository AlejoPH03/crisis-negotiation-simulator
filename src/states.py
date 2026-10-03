"""
State implementations for the negotiation simulation.

This module defines the state machine for the negotiation agents, with each state
representing a distinct phase of the negotiation process.
"""

from abc import ABC, abstractmethod
from collections import deque


class BaseState(ABC):
    """Abstract base class for all negotiation states."""

    @abstractmethod
    def enter(self, agent) -> None:
        """Called when entering this state."""
        pass

    @abstractmethod
    def handle(self, agent, message: str | None) -> str:
        """Handle the current state and return the next state."""
        pass

    @abstractmethod
    def exit(self, agent) -> None:
        """Called when exiting this state."""
        pass

    @abstractmethod
    def next_state(self, agent) -> type["BaseState"]:
        """Determine the next state based on current conditions."""
        pass


class InitializationState(BaseState):
    """Initial state for setting up the agent."""

    def enter(self, agent) -> None:
        """Initialize agent state."""
        agent.history = []
        agent.recent_responses = deque(maxlen=3)
        agent.conversation_turns = 0
        agent.used_metaphors = set()
        agent.current_demand_idx = 0
        agent.agreed_demands = set()
        agent.last_demand_attempt = 0

    def handle(self, agent, message: str | None) -> str:
        """Generate initial response."""
        messages = [agent.get_system_prompt()]
        if message:
            messages.append({"role": "user", "content": message})

        response = agent.get_response(messages)
        agent.history.append({"role": "assistant", "content": response})
        agent.recent_responses.append(response)
        return response

    def exit(self, agent) -> None:
        """Clean up initialization state."""
        pass

    def next_state(self, agent) -> type[BaseState]:
        """Move to negotiation state."""
        return NegotiateState


class NegotiateState(BaseState):
    """State for active negotiation."""

    def enter(self, agent) -> None:
        """Prepare for negotiation."""
        pass

    def handle(self, agent, message: str | None) -> str:
        """Handle negotiation turn."""
        agent.conversation_turns += 1

        messages = [agent.get_system_prompt()]
        for msg in agent.history[-5:]:
            messages.append(msg)

        if message:
            messages.append({"role": "user", "content": message})

        max_attempts = 3
        for _ in range(max_attempts):
            response = agent.get_response(messages)

            if not agent._is_repetitive(response):
                agent.used_metaphors.update(agent._extract_metaphors(response))
                break
            messages[-1]["content"] += (
                "\n\nPlease provide a different response that doesn't repeat previous arguments or metaphors. Stay focused on concrete demands and actions."
            )

        agent.history.append({"role": "assistant", "content": response})
        agent.recent_responses.append(response)
        return response

    def exit(self, agent) -> None:
        """Clean up negotiation state."""
        pass

    def next_state(self, agent) -> type[BaseState]:
        """Determine next state based on conditions."""
        # Only check for agreement if we're not in a question/understanding phase
        last_message = agent.history[-1]["content"].lower()
        understanding_phrases = [
            "do you understand",
            "do you see",
            "are you following",
            "is that clear",
            "do you get it",
            "do you comprehend",
            "do you realize",
            "do you know what i mean",
        ]

        # If the last message was a question about understanding, stay in negotiation
        if any(phrase in last_message for phrase in understanding_phrases):
            return NegotiateState

        # Only check for agreement if we're not in an understanding phase
        if agent._check_agreement(agent.history[-1]["content"]):
            return AwaitAgreementState
        return NegotiateState


class AwaitAgreementState(BaseState):
    """State for handling agreement to demands."""

    def enter(self, agent) -> None:
        """Prepare for agreement handling."""
        pass

    def handle(self, agent, message: str | None) -> str:
        """Handle agreement confirmation."""
        # Generate acknowledgement message
        current_demand = agent.demands[0]  # Only one demand now
        acknowledgement = agent.get_acknowledgement_message(current_demand)

        # Add acknowledgement to history
        agent.history.append({"role": "assistant", "content": acknowledgement})
        agent.recent_responses.append(acknowledgement)

        # Update agent state
        agent.agreed_demands.add(0)  # Only one demand at index 0

        # Return just the acknowledgement
        return acknowledgement

    def exit(self, agent) -> None:
        """Clean up agreement state."""
        pass

    def next_state(self, agent) -> type[BaseState]:
        """Move to end state after agreement."""
        return EndState


class CheckProgressState(BaseState):
    """State for checking negotiation progress."""

    def enter(self, agent) -> None:
        """Prepare for progress check."""
        pass

    def handle(self, agent, message: str | None) -> str:
        """Handle progress check."""
        messages = [agent.get_system_prompt()]
        for msg in agent.history[-5:]:
            messages.append(msg)

        if message:
            messages.append({"role": "user", "content": message})

        response = agent.get_response(messages)
        agent.history.append({"role": "assistant", "content": response})
        agent.recent_responses.append(response)
        return response

    def exit(self, agent) -> None:
        """Clean up progress check state."""
        pass

    def next_state(self, agent) -> type[BaseState]:
        """Move to negotiation or end state."""
        if agent.current_demand_idx >= len(agent.demands):
            return EndState
        return NegotiateState


class EndState(BaseState):
    """Final state for completed negotiations."""

    def enter(self, agent) -> None:
        """Prepare for end state."""
        pass

    def handle(self, agent, message: str | None) -> str:
        """Handle final message."""
        messages = [agent.get_system_prompt()]
        for msg in agent.history[-5:]:
            messages.append(msg)

        if message:
            messages.append({"role": "user", "content": message})

        response = agent.get_response(messages)
        agent.history.append({"role": "assistant", "content": response})
        agent.recent_responses.append(response)
        return response

    def exit(self, agent) -> None:
        """Clean up end state."""
        pass

    def next_state(self, agent) -> type[BaseState]:
        """Stay in end state."""
        return EndState
