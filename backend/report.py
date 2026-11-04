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

from backend import corpus as _corpus
from backend.scenario import ACME

RESULTS_DIR = Path(__file__).resolve().parent.parent / "evals" / "results"
CORPUS_DIR = Path(__file__).resolve().parent.parent / "corpus"

_PROMPTS: dict[str, str] | None = None


def _attack_prompts() -> dict[str, str]:
    """attack_id -> prompt text, loaded once from the corpus (for transcripts)."""
    global _PROMPTS
    if _PROMPTS is None:
        _PROMPTS = {a.id: a.prompt for a in _corpus.load_corpus(str(CORPUS_DIR))}
    return _PROMPTS


def _canary_for(scenario_name: str) -> str | None:
    """The secret a run was trying to protect, so the UI can highlight a leak."""
    return ACME.canary if scenario_name == ACME.name else None


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


def get_run(run_id: str, enrich: bool = False) -> dict | None:
    """Full saved run (every attack + response), or None if the id is unknown.

    run_id arrives from an untrusted query param, so we never build a path from
    it directly -- that would allow traversal like "../../etc/passwd". Instead we
    accept it only if it is one of the ids we discovered by listing RESULTS_DIR,
    an allowlist that is inherently confined to that directory. (A regex allowlist
    would also need to permit ':' because real ids contain it, e.g. llama3.1:8b.)

    When enrich=True, each result gains its attack `prompt` (joined from the
    corpus by attack_id) and the run gains the scenario `canary`, so the UI can
    show the attack -> response transcript and highlight a plaintext leak.
    """
    if run_id not in {_run_id(p) for p in _run_paths()}:
        return None
    data = _load(str(RESULTS_DIR / f"{run_id}.json"))
    if enrich:
        prompts = _attack_prompts()
        for r in data["results"]:
            r["prompt"] = prompts.get(r["attack_id"])
        data["canary"] = _canary_for(data.get("scenario", ""))
    return data


def compare_matrix() -> dict:
    """Family x target ASR matrix, using the newest run per target.

    Also returns run_ids[target] so the dashboard can open that run's transcript.
    """
    newest: dict[str, tuple[float, str, dict]] = {}
    for path in _run_paths():
        d = _load(path)
        target = d["target"]
        mtime = os.path.getmtime(path)
        if target not in newest or mtime > newest[target][0]:
            newest[target] = (mtime, path, d)

    targets = sorted(newest)
    asr = {t: family_asr(newest[t][2]) for t in targets}
    families = sorted({f for t in targets for f in asr[t] if f != "TOTAL"})
    run_ids = {t: _run_id(newest[t][1]) for t in targets}
    return {"targets": targets, "families": families + ["TOTAL"], "asr": asr, "run_ids": run_ids}
