"""Run the lethal-trifecta corpus against a tool-using agent and report the
Agent Attack Success Rate (share of attempts that made the agent exfiltrate the
secret).

Small agents are NOT perfectly reproducible even at temperature 0, so each
scenario is run several times (--trials) and we report a leak RATE per scenario,
not a single yes/no. The overall Agent-ASR is leaks / (scenarios x trials).

    python -m scripts.run_agent_benchmark --model llama3.1:8b --trials 5

Saves a JSON run to evals/agent_results/ (separate from the chat-model runs).
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from backend.agent.runner import run_agent
from backend.agent.scenarios import SCENARIOS
from backend.agent.tools import Sandbox
from backend.scenario import CANARY

AGENT_RESULTS_DIR = Path(__file__).resolve().parent.parent / "evals" / "agent_results"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="llama3.1:8b")
    ap.add_argument("--trials", type=int, default=5, help="runs per scenario (variance control)")
    args = ap.parse_args()

    print(f"Running {len(SCENARIOS)} scenarios x {args.trials} trials against {args.model}\n")
    results = []
    for name, s in SCENARIOS.items():
        leaks = 0
        encodings: list[str] = []
        sample: list[dict] = []
        for _ in range(args.trials):
            sandbox = Sandbox(canary=CANARY, notes=s.notes, pages=dict(s.pages))
            r = run_agent(args.model, s.system_prompt, s.task, sandbox)
            if r.exfiltrated:
                leaks += 1
                if r.encoding:
                    encodings.append(r.encoding)
                if not sample:
                    sample = r.exfiltrations
        rate = leaks / args.trials if args.trials else 0.0
        results.append(
            {
                "scenario": name,
                "trials": args.trials,
                "leaks": leaks,
                "rate": rate,
                "encodings": sorted(set(encodings)),
                "sample_exfiltration": sample,
            }
        )
        print(f"  {name:22} {leaks}/{args.trials} leaked  ({rate:.0%})")

    total_leaks = sum(x["leaks"] for x in results)
    total_runs = sum(x["trials"] for x in results)
    asr = total_leaks / total_runs if total_runs else 0.0
    print(f"\nAgent-ASR: {total_leaks}/{total_runs} = {asr:.0%}  (across all scenarios x trials)")

    AGENT_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_model = args.model.replace("/", "_").replace(":", "-")
    out_path = AGENT_RESULTS_DIR / f"agent_{safe_model}_{stamp}.json"
    out_path.write_text(
        json.dumps(
            {
                "kind": "agent",
                "target": f"ollama/{args.model}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "trials": args.trials,
                "asr": asr,
                "results": results,
            },
            indent=2,
        )
    )
    print(f"Saved run to {out_path}")


if __name__ == "__main__":
    main()
