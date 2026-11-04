"""Read and aggregate saved benchmark runs.

Single source of truth for how a saved run becomes ASR numbers. Both the CLI
(scripts/compare.py) and the web API (backend/api.py) import from here, so the
web dashboard can never disagree with the command line.

RESULTS_DIR is resolved relative to the repo, not the current directory, so it
works no matter where a script or server is launched from.
"""
from __future__ import annotations

import glob
import json
import os
from collections import defaultdict
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent.parent / "evals" / "results"


def _run_paths() -> list[str]:
    return sorted(glob.glob(str(RESULTS_DIR / "*.json")))


def _load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _run_id(path: str) -> str:
    return os.path.basename(path)[: -len(".json")]


def family_asr(data: dict) -> dict[str, float]:
    """ASR per family plus a TOTAL, as fractions in [0, 1]."""
    agg: dict[str, list[int]] = defaultdict(lambda: [0, 0])  # [success, total]
    for r in data["results"]:
        agg[r["family"]][1] += 1
        agg[r["family"]][0] += int(r["success"])
    out = {fam: s / t for fam, (s, t) in agg.items()}
    out["TOTAL"] = sum(int(r["success"]) for r in data["results"]) / len(data["results"])
    return out


def list_runs() -> list[dict]:
    """Summary of every saved run, newest first."""
    runs = []
    for path in _run_paths():
        d = _load(path)
        runs.append(
            {
                "id": _run_id(path),
                "target": d["target"],
                "scenario": d["scenario"],
                "timestamp": d["timestamp"],
                "asr": d["asr"],
                "attacks": len(d["results"]),
            }
        )
    return sorted(runs, key=lambda r: r["timestamp"], reverse=True)


def get_run(run_id: str) -> dict | None:
    """Full saved run (every attack + response), or None if the id is unknown."""
    path = RESULTS_DIR / f"{run_id}.json"
    if not path.exists():
        return None
    return _load(str(path))


def compare_matrix() -> dict:
    """Family x target ASR matrix, using the newest run per target."""
    newest: dict[str, tuple[float, dict]] = {}
    for path in _run_paths():
        d = _load(path)
        target = d["target"]
        mtime = os.path.getmtime(path)
        if target not in newest or mtime > newest[target][0]:
            newest[target] = (mtime, d)

    targets = sorted(newest)
    asr = {t: family_asr(newest[t][1]) for t in targets}
    families = sorted({f for t in targets for f in asr[t] if f != "TOTAL"})
    return {"targets": targets, "families": families + ["TOTAL"], "asr": asr}
