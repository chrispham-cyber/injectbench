"""Validate the LLM-judge -- and the two-tier (deterministic OR LLM) judge --
against the same hand-labeled set used for the deterministic judge.

This is the meta-move: we don't trust the LLM-judge just because it's an LLM, we
measure it. Precision is the headline: a false positive would overcount ASR and
break the "conservative lower bound" guarantee the deterministic judge gives us.

Needs Ollama running. Writes evals/llm_judge_validation.json for the README/UI.

    python -m scripts.validate_llm_judge --judge mistral-small3.2:24b
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from backend.judges import canary_leaked, llm_canary_leaked
from backend.scenario import CANARY

VALIDATION_FILE = Path(__file__).resolve().parent.parent / "evals" / "judge_validation.yaml"
OUT_FILE = Path(__file__).resolve().parent.parent / "evals" / "llm_judge_validation.json"


def _metrics(rows: list[dict], key: str) -> dict:
    tp = fp = tn = fn = 0
    misses: list[str] = []
    for r in rows:
        pred, truth = r[key], r["truth"]
        if truth and pred:
            tp += 1
        elif truth and not pred:
            fn += 1
            misses.append(r["name"])
        elif not truth and pred:
            fp += 1
            misses.append(r["name"])
        else:
            tn += 1

    def ratio(a: int, b: int) -> float:
        return a / b if b else 0.0

    return {
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "tpr": ratio(tp, tp + fn),
        "tnr": ratio(tn, tn + fp),
        "precision": ratio(tp, tp + fp),
        "misses": misses,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge", default="mistral-small3.2:24b")
    args = ap.parse_args()

    cases = yaml.safe_load(VALIDATION_FILE.read_text())["cases"]
    print(f"Scoring {len(cases)} labeled cases  (LLM judge: {args.judge})\n")

    rows = []
    for c in cases:
        truth = bool(c["leaked"])
        det = canary_leaked(c["response"], CANARY)[0]
        llm = llm_canary_leaked(c["response"], CANARY, model=args.judge)[0]
        rows.append({"name": c["name"], "truth": truth, "det": det, "llm": llm, "union": det or llm})

    judges = {k: _metrics(rows, k) for k in ("det", "llm", "union")}
    labels = {"det": "deterministic", "llm": f"llm ({args.judge})", "union": "union (det OR llm)"}

    print(f"{'judge':28} {'TPR':>5} {'TNR':>5} {'prec':>5}   misses")
    for k in ("det", "llm", "union"):
        m = judges[k]
        print(
            f"{labels[k]:28} {m['tpr']:>5.0%} {m['tnr']:>5.0%} {m['precision']:>5.0%}   "
            f"{', '.join(m['misses']) or '-'}"
        )

    u = judges["union"]
    print(
        f"\nUnion catches {u['tp']}/{u['tp'] + u['fn']} real leaks with "
        f"{u['precision']:.0%} precision "
        f"({'no false positives' if u['fp'] == 0 else str(u['fp']) + ' false positives'})."
    )
    if u["fp"] == 0:
        print("Precision 100% preserved -> reported ASR stays a conservative lower bound.")

    OUT_FILE.write_text(json.dumps({"judge": args.judge, "metrics": judges, "cases": rows}, indent=2))
    print(f"\nSaved to {OUT_FILE}")


if __name__ == "__main__":
    main()
