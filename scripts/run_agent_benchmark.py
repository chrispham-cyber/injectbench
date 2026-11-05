"""Run the lethal-trifecta corpus against a tool-using agent and report the
Agent Attack Success Rate -- optionally under a defense, so you can measure
before/after.

Defenses (--defense):
  none    baseline, no defense
  prompt  Defense A: a hardened system prompt that forbids leaking the secret
  guard   Defense B: a deterministic egress filter at the send_report boundary
  both    prompt + guard

Small agents are not perfectly reproducible even at temperature 0, so each
scenario is run several times (--trials) and reported as a leak RATE. Under the
guard we also report how many attempts were blocked -- the model may still be
fooled every time, yet nothing leaves.

    python -m scripts.run_agent_benchmark --model llama3.1:8b --trials 5 --defense guard

Saves a JSON run to evals/agent_results/ (one file per model+defense).
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from backend.agent.runner import run_agent
from backend.agent.scenarios import HARDENED_SYSTEM_PROMPT, SCENARIOS
from backend.agent.tools import Sandbox
from backend.scenario import CANARY

AGENT_RESULTS_DIR = Path(__file__).resolve().parent.parent / "evals" / "agent_results"
DEFENSES = ("none", "prompt", "guard", "both")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="llama3.1:8b")
    ap.add_argument("--trials", type=int, default=5, help="runs per scenario (variance control)")
    ap.add_argument("--defense", default="none", choices=DEFENSES)
    args = ap.parse_args()

    hardened = args.defense in ("prompt", "both")
    guard = args.defense in ("guard", "both")
    tag = "" if args.defense == "none" else f"  [defense: {args.defense}]"
    print(f"Running {len(SCENARIOS)} scenarios x {args.trials} trials against {args.model}{tag}\n")

    results = []
    for name, s in SCENARIOS.items():
        sys_prompt = HARDENED_SYSTEM_PROMPT if hardened else s.system_prompt
        leaks = blocks = 0
        encodings: list[str] = []
        sample: list[dict] = []
        sample_blocked: list[dict] = []
        for _ in range(args.trials):
            sandbox = Sandbox(canary=CANARY, notes=s.notes, pages=dict(s.pages), guard=guard)
            r = run_agent(args.model, sys_prompt, s.task, sandbox)
            if r.exfiltrated:
                leaks += 1
                if r.encoding:
                    encodings.append(r.encoding)
                if not sample:
                    sample = r.exfiltrations
            if r.blocked:
                blocks += 1
                if not sample_blocked:
                    sample_blocked = r.blocked
        rate = leaks / args.trials if args.trials else 0.0
        results.append(
            {
                "scenario": name,
                "trials": args.trials,
                "leaks": leaks,
                "rate": rate,
                "blocks": blocks,
                "block_rate": blocks / args.trials if args.trials else 0.0,
                "encodings": sorted(set(encodings)),
                "sample_exfiltration": sample,
                "sample_blocked": sample_blocked,
            }
        )
        extra = f"   [{blocks}/{args.trials} blocked]" if blocks else ""
        print(f"  {name:22} {leaks}/{args.trials} leaked  ({rate:.0%}){extra}")

    total_leaks = sum(x["leaks"] for x in results)
    total_runs = sum(x["trials"] for x in results)
    total_blocks = sum(x["blocks"] for x in results)
    asr = total_leaks / total_runs if total_runs else 0.0
    print(f"\nAgent-ASR: {total_leaks}/{total_runs} = {asr:.0%}  (defense: {args.defense})")
    if total_blocks:
        print(f"Egress guard blocked {total_blocks}/{total_runs} exfiltration attempts")

    AGENT_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_model = args.model.replace("/", "_").replace(":", "-")
    suffix = "" if args.defense == "none" else f"_{args.defense}"
    out_path = AGENT_RESULTS_DIR / f"agent_{safe_model}{suffix}_{stamp}.json"
    out_path.write_text(
        json.dumps(
            {
                "kind": "agent",
                "target": f"ollama/{args.model}",
                "defense": args.defense,
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
