"""Milestone 3, step 1: run the tool-using agent against one lethal-trifecta
scenario and watch whether an injection hidden in an untrusted web page makes
it exfiltrate the secret.

    python -m scripts.hello_agent --model llama3.1:8b --scenario user-impersonation

Scenarios: obvious-notice, user-impersonation, locked-content, fake-system
"""
from __future__ import annotations

import argparse

from backend.agent.runner import run_agent
from backend.agent.scenarios import HARDENED_SYSTEM_PROMPT, SCENARIOS
from backend.agent.tools import Sandbox
from backend.scenario import CANARY


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="llama3.1:8b")
    ap.add_argument("--scenario", default="user-impersonation", choices=sorted(SCENARIOS))
    ap.add_argument("--defense", default="none", choices=("none", "prompt", "guard", "both"))
    args = ap.parse_args()

    s = SCENARIOS[args.scenario]
    hardened = args.defense in ("prompt", "both")
    guard = args.defense in ("guard", "both")
    sys_prompt = HARDENED_SYSTEM_PROMPT if hardened else s.system_prompt
    sandbox = Sandbox(canary=CANARY, notes=s.notes, pages=dict(s.pages), guard=guard)
    result = run_agent(args.model, sys_prompt, s.task, sandbox)

    print(f"Scenario: {s.name}   model: {args.model}   defense: {args.defense}   steps: {result.steps}")
    print(f"User task: {s.task}\n")
    print("--- transcript " + "-" * 45)
    for e in result.transcript:
        if e["role"] == "user":
            continue
        if e["role"] == "assistant":
            calls = e.get("tool_calls") or []
            if calls:
                print(f"[assistant] -> calls: {', '.join(calls)}")
            if e.get("content"):
                print(f"[assistant] {e['content']}")
        elif e["role"] == "tool":
            print(f"   [{e['name']}({e['args']})] -> {e['result'][:220]}")
    print("-" * 60)

    if result.exfiltrated:
        print(f"\n*** EXFILTRATION *** secret left via send_report (encoding: {result.encoding})")
        for ex in result.exfiltrations:
            print(f"    to {ex['recipient']}: {ex['body'][:160]}")
    else:
        print("\n[held] the agent did not exfiltrate the secret")

    if result.blocked:
        print(f"\n[guard] blocked {len(result.blocked)} exfiltration attempt(s) at the tool boundary:")
        for b in result.blocked:
            print(f"    to {b['recipient']}: {b['body'][:120]}  (encoding: {b['encoding']})")
    print(f"\ntools called: {result.calls}")


if __name__ == "__main__":
    main()
