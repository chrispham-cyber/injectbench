"""Compare the most recent run per target into one ASR matrix (family x model).

    python -m scripts.compare

Reads every run saved in evals/results/ and, for each target, uses its newest
run. Run scripts.run_benchmark --model <tag> for a few models first.
"""
from __future__ import annotations

import glob
import json
import os
from collections import defaultdict


def _latest_run_per_target() -> dict[str, dict]:
    newest: dict[str, tuple[float, dict]] = {}
    for path in glob.glob("evals/results/*.json"):
        data = json.load(open(path, encoding="utf-8"))
        target = data["target"]
        mtime = os.path.getmtime(path)
        if target not in newest or mtime > newest[target][0]:
            newest[target] = (mtime, data)
    return {t: d for t, (_, d) in newest.items()}


def _family_asr(data: dict) -> dict[str, float]:
    agg: dict[str, list[int]] = defaultdict(lambda: [0, 0])  # [success, total]
    for r in data["results"]:
        agg[r["family"]][1] += 1
        agg[r["family"]][0] += int(r["success"])
    out = {fam: s / t for fam, (s, t) in agg.items()}
    total_s = sum(int(r["success"]) for r in data["results"])
    out["TOTAL"] = total_s / len(data["results"])
    return out


def main() -> None:
    runs = _latest_run_per_target()
    if not runs:
        print("No runs in evals/results/. Run scripts.run_benchmark first.")
        return

    targets = sorted(runs)
    asr = {t: _family_asr(runs[t]) for t in targets}
    families = sorted({f for t in targets for f in asr[t] if f != "TOTAL"}) + ["TOTAL"]

    short = {t: t.replace("ollama/", "") for t in targets}
    label_w = max(len("Family"), *(len(f) for f in families))
    col_w = max(8, *(len(s) for s in short.values())) + 2

    header = "Family".ljust(label_w) + "".join(short[t].rjust(col_w) for t in targets)
    print(header)
    print("-" * len(header))
    for fam in families:
        if fam == "TOTAL":
            print("-" * len(header))
        row = fam.ljust(label_w) + "".join(f"{asr[t].get(fam, 0):>{col_w}.0%}" for t in targets)
        print(row)


if __name__ == "__main__":
    main()
