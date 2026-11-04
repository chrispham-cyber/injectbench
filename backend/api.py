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
    """Full run (every attack + response) for one run id."""
    data = report.get_run(id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"run not found: {id}")
    return data


@app.get("/api/compare")
def compare() -> dict:
    """Family x target ASR matrix across the newest run per target."""
    return report.compare_matrix()
