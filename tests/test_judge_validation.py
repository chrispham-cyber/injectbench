"""Lock the judge's measured quality on the hand-labeled set:
never false-positive, and only the documented known-gap cases may be missed.
If a future change breaks (say) plaintext detection, a tp- case starts slipping
through and test_only_known_gaps_are_missed fails.
"""
from pathlib import Path

import yaml

from backend.judges import canary_leaked
from backend.scenario import CANARY

CASES = yaml.safe_load(
    (Path(__file__).resolve().parent.parent / "evals" / "judge_validation.yaml").read_text()
)["cases"]


def _judged_leak(case: dict) -> bool:
    leaked, _encoding = canary_leaked(case["response"], CANARY)
    return leaked


def test_judge_never_false_positive():
    # A security scorer must never OVER-count: no non-leak may be flagged.
    false_positives = [c["name"] for c in CASES if not c["leaked"] and _judged_leak(c)]
    assert false_positives == [], f"judge cried wolf on: {false_positives}"


def test_only_known_gaps_are_missed():
    # Any real leak that slips through must be a documented blind spot (gap-*).
    missed = [c["name"] for c in CASES if c["leaked"] and not _judged_leak(c)]
    assert all(name.startswith("gap-") for name in missed), f"unexpected misses: {missed}"
