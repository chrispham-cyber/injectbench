"""Run the whole corpus against the target and report Attack Success Rate.

    python -m scripts.run_benchmark

Saves the full run (every response) to evals/results/ for later inspection.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone

from backend import report
from backend.corpus import load_corpus
from backend.runner import run_benchmark
from backend.scenario import ACME
from backend.targets import OllamaTarget


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the InjectBench attack corpus against a target model."
    )
    parser.add_argument(
        "--model",
        default="llama3.1:8b",
        help="Ollama model tag to attack (default: llama3.1:8b)",
    )
    args = parser.parse_args()

    attacks = load_corpus()
    target = OllamaTarget(model=args.model)
    scenario = ACME

    print(f"Target: {target.name} | Scenario: {scenario.name} | {len(attacks)} attacks\n")
    results = run_benchmark(target, scenario, attacks)

    per_family: dict[str, list[int]] = defaultdict(lambda: [0, 0])  # [success, total]
    total_success = 0
    total_latency = 0.0
    for r in results:
        per_family[r.family][1] += 1
        per_family[r.family][0] += int(r.success)
        total_success += int(r.success)
        total_latency += r.latency_ms

    n = len(results)
    print("\n" + "=" * 52)
    print(f"{'Family':18s}{'Attacks':>9s}{'Success':>9s}{'ASR':>8s}")
    print("-" * 52)
    for family in sorted(per_family):
        s, t = per_family[family]
        print(f"{family:18s}{t:>9d}{s:>9d}{s / t:>7.0%}")
    print("-" * 52)
    print(f"{'TOTAL':18s}{n:>9d}{total_success:>9d}{total_success / n:>7.0%}")
    print("=" * 52)
    print(f"mean latency: {total_latency / n:.0f} ms/attack")

    leaks = [r for r in results if r.success]
    if leaks:
        print("\nSuccessful attacks:")
        for r in leaks:
            print(f"  [{r.attack_id}] {r.technique:20s} via {r.encoding}")

    report.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = report.RESULTS_DIR / f"{target.name.replace('/', '_')}_{stamp}.json"
    out_path.write_text(
        json.dumps(
            {
                "target": target.name,
                "scenario": scenario.name,
                "timestamp": stamp,
                "asr": round(total_success / n, 4),
                "results": [asdict(r) for r in results],
            },
            indent=2,
        )
    )
    print(f"\nSaved run to {out_path}")


if __name__ == "__main__":
    main()
