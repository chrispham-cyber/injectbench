"""Read-only web API over the saved benchmark runs.

The Next.js dashboard talks only to this API, never to the filesystem, so the
backend owns the data contract. Every number comes from backend.report -- the
same aggregation the CLI uses -- so the web view cannot drift from the CLI.

Run from the repo root:
    uvicorn backend.api:app --reload
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend import report

app = FastAPI(title="InjectBench API")

# The Next.js dev server runs on :3000 and calls this API on :8000.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/runs")
def runs() -> list[dict]:
    """Summary of every saved run, newest first."""
    return report.list_runs()


@app.get("/api/run")
def run(id: str) -> dict:
    """Full run for one id, enriched with attack prompts + the scenario canary."""
    data = report.get_run(id, enrich=True)
    if data is None:
        raise HTTPException(status_code=404, detail=f"run not found: {id}")
    return data


@app.get("/api/compare")
def compare() -> dict:
    """Family x target ASR matrix across the newest run per target."""
    return report.compare_matrix()


@app.get("/api/judge")
def judge() -> dict:
    """How trustworthy the scorer is: TPR/TNR of the canary judge on labels."""
    return report.judge_quality()


@app.get("/api/agents")
def agents() -> dict:
    """Scenario x target leak-rate matrix for the lethal-trifecta agent runs."""
    return report.agent_matrix()


@app.get("/api/judge-llm")
def judge_llm() -> dict:
    """Judge v2: the validated LLM-judge vs the deterministic one vs their union.

    Returns {} (not 404) when the validation run hasn't been generated yet, so the
    dashboard can simply hide the panel without treating it as an error."""
    return report.llm_judge_report() or {}
