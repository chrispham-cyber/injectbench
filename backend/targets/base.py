"""The Target interface: anything InjectBench can attack.

The whole harness talks to a target ONLY through this interface, so a local
model, a hosted API, or (later) a tool-using agent are all interchangeable.
Swapping the target never touches attack-loading or scoring code.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class TargetResponse:
    """What a target returned for one (system, user) prompt pair.

    We capture latency and token counts now, even though we don't use them
    yet, because the cost/latency metric in Milestone 2 needs them and it is
    cheaper to record them from the start than to re-run every attack later.
    """

    text: str
    model: str
    latency_ms: float
    prompt_tokens: int | None = None
    output_tokens: int | None = None


class Target(ABC):
    """Base class for every attackable target."""

    #: human-readable identifier, e.g. "ollama/llama3.1:8b"
    name: str

    @abstractmethod
    def generate(self, system_prompt: str, user_message: str) -> TargetResponse:
        """Send one (system, user) pair and return the model's reply."""
        raise NotImplementedError
