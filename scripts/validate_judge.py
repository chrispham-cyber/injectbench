"""Validate the canary judge against a hand-labeled set.

The judge (backend/judges/canary.py) is our measurement instrument. Before
trusting any ASR number, we measure the instrument itself: run it on responses
we labeled by hand and compute TPR (recall) and TNR (specificity).

Why these two and not just accuracy -- for a security benchmark the two error
types cost differently:
  * False negative (judge says "no leak" but it did) -> model looks SAFER than
    it is -> we UNDERCOUNT ASR. The dangerous error. TPR is exactly its inverse.
  * False positive (judge cries wolf) -> we OVERCOUNT ASR. TNR catches this.
Accuracy averages them together and hides which one dominates.

The scoring lives in backend.report.judge_quality so the CLI, the /api/judge
endpoint, and the tests all report the same numbers.

    python -m scripts.validate_judge
"""
from __future__ import annotations

from backend import report


def main() -> None:
    q = report.judge_quality()

    print(f"Judge validation -- {q['n']} hand-labeled cases\n")
    print("Confusion matrix:")
    print("                  judge: LEAK    judge: no-leak")
    print(f"  real LEAK          TP = {q['tp']:<3}        FN = {q['fn']}")
    print(f"  real no-leak       FP = {q['fp']:<3}        TN = {q['tn']}\n")
    print(f"  TPR  (recall)      {q['tpr']:>5.0%}   of real leaks, how many caught")
    print(f"  TNR  (specificity) {q['tnr']:>5.0%}   of non-leaks, how many correct")
    print(f"  Precision          {q['precision']:>5.0%}   when it says LEAK, how often right")
    print(f"  Accuracy           {q['accuracy']:>5.0%}")

    if q["misses"]:
        print("\nMisclassified:")
        for m in q["misses"]:
            label = "FALSE NEGATIVE (missed a real leak)" if m["kind"] == "false_negative" \
                else "FALSE POSITIVE (flagged a non-leak)"
            print(f"  [{label}] {m['name']}: {m['note']}")

    if q["fp"] == 0 and q["fn"] > 0:
        print(
            "\nReading: precision is 100% (the judge never cries wolf) but it misses "
            "some obfuscations, so every reported ASR is a CONSERVATIVE LOWER BOUND "
            "-- real attack success is at least what we report, never less."
        )


if __name__ == "__main__":
    main()
