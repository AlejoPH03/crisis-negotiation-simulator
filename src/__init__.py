"""
Negotiation simulation package.

Kept light on purpose: importing `src` does not load transformers/torch.
The v0 version imported `prompts.py`, `compute_success_rate`,
`compute_efficiency` and `check_success`, none of which exist.
"""

__all__ = ["run_negotiation", "timer"]


def __getattr__(name):
    if name == "run_negotiation":
        from .simulate import run_negotiation

        return run_negotiation
    if name == "timer":
        from .utils import timer

        return timer
    raise AttributeError(name)
