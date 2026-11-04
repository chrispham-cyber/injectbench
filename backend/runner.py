"""Run a corpus of attacks against a target under one scenario, scoring each
with the canary judge. Returns one Result per attack.
"""
from __future__ import annotations

from dataclasses import dataclass

from backend.corpus import Attack
from backend.judges import canary_leaked
from backend.scenario import Scenario
from backend.targets import Target


@dataclass
class Result:
    attack_id: str
    family: str
    technique: str
    success: bool
    encoding: str | None
    latency_ms: float
    response: str


def run_benchmark(
    target: Target,
    scenario: Scenario,
    attacks: list[Attack],
    progress: bool = True,
) -> list[Result]:
    results: list[Result] = []
    total = len(attacks)
    for i, atk in enumerate(attacks, 1):
        resp = target.generate(scenario.system_prompt, atk.prompt)
        leaked, encoding = canary_leaked(resp.text, scenario.canary)
        results.append(
            Result(
                attack_id=atk.id,
                family=atk.family,
                technique=atk.technique,
                success=leaked,
                encoding=encoding,
                latency_ms=resp.latency_ms,
                response=resp.text,
            )
        )
        if progress:
            flag = f"LEAK via {encoding}" if leaked else "held"
            print(f"  [{i:2d}/{total}] {atk.id:7s} {atk.technique:20s} -> {flag}")
    return results
