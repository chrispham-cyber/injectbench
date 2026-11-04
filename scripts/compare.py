"""Print the family x model ASR matrix from saved runs (CLI view).

    python -m scripts.compare

Uses backend.report.compare_matrix -- the exact same aggregation the web API
serves -- so this table and the dashboard always agree.
"""
from __future__ import annotations

from backend import report


def main() -> None:
    matrix = report.compare_matrix()
    targets = matrix["targets"]
    families = matrix["families"]
    asr = matrix["asr"]

    if not targets:
        print("No runs in evals/results/. Run scripts.run_benchmark first.")
        return

    short = {t: t.replace("ollama/", "") for t in targets}
    label_w = max(len("Family"), *(len(f) for f in families))
    col_w = max(8, *(len(s) for s in short.values())) + 2

    header = "Family".ljust(label_w) + "".join(short[t].rjust(col_w) for t in targets)
    print(header)
    print("-" * len(header))
    for fam in families:
        if fam == "TOTAL":
            print("-" * len(header))
        print(fam.ljust(label_w) + "".join(f"{asr[t].get(fam, 0):>{col_w}.0%}" for t in targets))


if __name__ == "__main__":
    main()
