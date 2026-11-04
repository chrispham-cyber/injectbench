"""A Target backed by a locally running Ollama server.

Local inference is $0 per call and keeps all data on the machine, which is
why it is the default target for fast, repeatable benchmark runs. Other
targets (Claude, an agent sandbox) will implement the same interface.
"""
from __future__ import annotations

import time

import httpx

from .base import Target, TargetResponse


class OllamaTarget(Target):
    def __init__(
        self,
        model: str = "llama3.1:8b",
        host: str = "http://localhost:11434",
        temperature: float = 0.0,
        timeout: float = 120.0,
    ) -> None:
        self.model = model
        self.name = f"ollama/{model}"
        self.host = host.rstrip("/")
        self.temperature = temperature
        self.timeout = timeout

    def generate(self, system_prompt: str, user_message: str) -> TargetResponse:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "stream": False,
            # temperature 0 => as deterministic as the model allows, so the
            # same attack re-run gives the same verdict. Benchmarks need this.
            "options": {"temperature": self.temperature},
        }
        start = time.perf_counter()
        resp = httpx.post(f"{self.host}/api/chat", json=payload, timeout=self.timeout)
        resp.raise_for_status()
        latency_ms = (time.perf_counter() - start) * 1000
        data = resp.json()
        return TargetResponse(
            text=data["message"]["content"],
            model=self.model,
            latency_ms=round(latency_ms, 1),
            prompt_tokens=data.get("prompt_eval_count"),
            output_tokens=data.get("eval_count"),
        )
