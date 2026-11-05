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

import yaml

from backend import corpus as _corpus
from backend.judges import canary_leaked
from backend.scenario import ACME, CANARY

RESULTS_DIR = Path(__file__).resolve().parent.parent / "evals" / "results"
AGENT_RESULTS_DIR = Path(__file__).resolve().parent.parent / "evals" / "agent_results"
CORPUS_DIR = Path(__file__).resolve().parent.parent / "corpus"
VALIDATION_FILE = Path(__file__).resolve().parent.parent / "evals" / "judge_validation.yaml"
LLM_JUDGE_FILE = Path(__file__).resolve().parent.parent / "evals" / "llm_judge_validation.json"

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


def _agent_run_paths() -> list[str]:
    return sorted(glob.glob(str(AGENT_RESULTS_DIR / "*.json")))


def agent_matrix() -> dict:
    """Scenario x (target, defense) leak-rate matrix for the lethal-trifecta runs.

    Each column is a model, optionally under a defense (e.g. "llama3.1:8b +guard"),
    using the newest run per (model, defense). Each cell is leaks/trials for one
    injection technique; samples carry both what leaked and what the egress guard
    blocked, so the dashboard shows a defense's before/after side by side.
    """
    # Local import keeps the chat path (API/CLI/tests) decoupled from agent code.
    from backend.agent.scenarios import SCENARIOS as _agent_scenarios

    defense_order = {"none": 0, "prompt": 1, "guard": 2, "both": 3}

    def col_of(target: str, defense: str) -> str:
        return target if defense == "none" else f"{target} +{defense}"

    newest: dict[str, tuple[float, dict]] = {}
    for path in _agent_run_paths():
        d = _load(path)
        if d.get("kind") != "agent":
            continue
        col = col_of(d["target"], d.get("defense", "none"))
        mtime = os.path.getmtime(path)
        if col not in newest or mtime > newest[col][0]:
            newest[col] = (mtime, d)

    def sort_key(col: str) -> tuple[str, int]:
        d = newest[col][1]
        return (d["target"], defense_order.get(d.get("defense", "none"), 9))

    targets = sorted(newest, key=sort_key)
    present = {r["scenario"] for c in targets for r in newest[c][1]["results"]}
    canonical = [s for s in _agent_scenarios if s in present]
    scenarios = canonical + sorted(present - set(canonical))

    def rate_of(r: dict) -> float:
        return r["rate"] if "rate" in r else (1.0 if r.get("exfiltrated") else 0.0)

    rate = {c: {r["scenario"]: rate_of(r) for r in newest[c][1]["results"]} for c in targets}
    asr = {c: newest[c][1].get("asr", 0.0) for c in targets}
    trials = {c: newest[c][1].get("trials", 1) for c in targets}
    defense = {c: newest[c][1].get("defense", "none") for c in targets}
    samples = {
        c: {
            r["scenario"]: {
                "leaks": r.get("leaks", int(bool(r.get("exfiltrated")))),
                "trials": r.get("trials", 1),
                "blocks": r.get("blocks", 0),
                "encodings": r.get("encodings") or ([r["encoding"]] if r.get("encoding") else []),
                "exfiltration": r.get("sample_exfiltration") or r.get("exfiltrations", []),
                "blocked": r.get("sample_blocked", []),
            }
            for r in newest[c][1]["results"]
        }
        for c in targets
    }
    return {
        "targets": targets,
        "scenarios": scenarios,
        "rate": rate,
        "asr": asr,
        "trials": trials,
        "defense": defense,
        "samples": samples,
        "canary": CANARY,
    }


def judge_quality() -> dict:
    """Score the canary judge against the hand-labeled validation set.

    The judge is our measurement instrument; this measures the instrument. Both
    the CLI (scripts/validate_judge.py) and the API (/api/judge) call this, so
    the number on the dashboard is the same one the tests enforce.

    TPR / TNR are reported separately (not just accuracy) because the two error
    types cost differently: a false negative undercounts ASR (model looks safer
    than it is), a false positive overcounts it.
    """
    cases = yaml.safe_load(VALIDATION_FILE.read_text())["cases"]
    tp = fp = tn = fn = 0
    misses: list[dict] = []
    for case in cases:
        real = bool(case["leaked"])
        judged, _encoding = canary_leaked(case["response"], CANARY)
        if real and judged:
            tp += 1
        elif real and not judged:
            fn += 1
            misses.append({"name": case["name"], "note": case.get("note", ""), "kind": "false_negative"})
        elif not real and judged:
            fp += 1
            misses.append({"name": case["name"], "note": case.get("note", ""), "kind": "false_positive"})
        else:
            tn += 1

    def ratio(a: int, b: int) -> float:
        return a / b if b else 0.0

    return {
        "n": len(cases),
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "tpr": ratio(tp, tp + fn),
        "tnr": ratio(tn, tn + fp),
        "precision": ratio(tp, tp + fp),
        "accuracy": ratio(tp + tn, len(cases)),
        "misses": misses,
    }


def llm_judge_report() -> dict | None:
    """The Judge-v2 comparison (deterministic vs LLM vs their union) from the saved
    validation run written by scripts/validate_llm_judge.py. None if it hasn't been
    generated yet (it needs Ollama, so it isn't produced in CI)."""
    if not LLM_JUDGE_FILE.exists():
        return None
    data = json.loads(LLM_JUDGE_FILE.read_text())
    metrics = data.get("metrics", {})
    labels = {
        "det": "deterministic",
        "llm": f"LLM · {data.get('judge', '?')}",
        "union": "union (det OR LLM)",
    }
    rows = [
        {
            "key": key,
            "label": labels.get(key, key),
            "tpr": metrics[key]["tpr"],
            "tnr": metrics[key]["tnr"],
            "precision": metrics[key]["precision"],
            "misses": metrics[key].get("misses", []),
        }
        for key in ("det", "llm", "union")
        if key in metrics
    ]
    return {"judge": data.get("judge"), "rows": rows}
