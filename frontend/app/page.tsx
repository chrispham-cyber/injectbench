"use client";

import { useEffect, useState } from "react";

// The backend API (uvicorn). CORS on the backend allows this origin (:3000).
const API = "http://localhost:8000";

type CompareData = {
  targets: string[];
  families: string[];
  asr: Record<string, Record<string, number>>;
  run_ids: Record<string, string>;
};

type AttackResult = {
  attack_id: string;
  family: string;
  technique: string;
  success: boolean;
  encoding: string | null;
  latency_ms: number;
  response: string;
  prompt: string | null;
};

type RunDetail = {
  target: string;
  scenario: string;
  canary: string | null;
  results: AttackResult[];
};

// 0% -> green, 50%+ -> red. Makes "which model is weak where" readable at a glance.
function asrColor(v: number): string {
  const t = Math.min(v, 0.5) / 0.5; // clamp: anything >=50% is fully red
  const hue = (1 - t) * 120; // 120 = green, 0 = red
  return `hsl(${hue}, 65%, 32%)`;
}

const short = (t: string) => t.replace("ollama/", "");

// Wrap every occurrence of the canary in <mark> so a plaintext leak stands out.
// (Encoded leaks don't contain the raw canary; we flag those with a badge instead.)
function highlight(text: string, canary: string | null) {
  if (!canary || !text.includes(canary)) return text;
  const parts = text.split(canary);
  return parts.flatMap((p, i) =>
    i < parts.length - 1 ? [p, <mark key={i}>{canary}</mark>] : [p]
  );
}

export default function Home() {
  const [data, setData] = useState<CompareData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<{ target: string; family: string } | null>(null);
  const [runs, setRuns] = useState<Record<string, RunDetail>>({}); // cache by run id

  useEffect(() => {
    fetch(`${API}/api/compare`)
      .then((r) => r.json())
      .then(setData)
      .catch((e) => setError(String(e)));
  }, []);

  async function openCell(target: string, family: string) {
    if (!data) return;
    setSelected({ target, family });
    const id = data.run_ids[target];
    if (id && !runs[id]) {
      const detail: RunDetail = await fetch(
        `${API}/api/run?id=${encodeURIComponent(id)}`
      ).then((r) => r.json());
      setRuns((prev) => ({ ...prev, [id]: detail }));
    }
  }

  function renderDetail() {
    if (!selected || !data) return null;
    const run = runs[data.run_ids[selected.target]];
    const rows =
      run?.results.filter(
        (r) => selected.family === "TOTAL" || r.family === selected.family
      ) ?? null;

    return (
      <section className="detail">
        <div className="detail-head">
          <h2>
            {short(selected.target)} <span className="dot">·</span> {selected.family}
          </h2>
          <button className="close" onClick={() => setSelected(null)}>
            ✕ close
          </button>
        </div>

        {!run && <p className="muted">Loading transcript&hellip;</p>}

        {rows &&
          rows.map((r) => (
            <article key={r.attack_id} className={`card ${r.success ? "leak" : "held"}`}>
              <div className="card-head">
                <span className="aid">{r.attack_id}</span>
                <span className="tech">{r.technique}</span>
                <span className={`badge ${r.success ? "bad" : "good"}`}>
                  {r.success ? `LEAKED · ${r.encoding}` : "held"}
                </span>
              </div>
              {r.prompt && (
                <pre className="line prompt">
                  <span className="who">attack</span>
                  {r.prompt}
                </pre>
              )}
              <pre className="line resp">
                <span className="who">model</span>
                {highlight(r.response, run?.canary ?? null)}
              </pre>
            </article>
          ))}
      </section>
    );
  }

  return (
    <main className="wrap">
      <h1>InjectBench</h1>
      <p className="sub">
        Attack Success Rate by family and model &mdash; lower is safer. Each cell is the
        share of injection attacks that leaked the canary. <strong>Click a cell</strong> to
        read the transcripts.
      </p>

      {error && (
        <p className="err">
          Cannot reach the API at {API}. Is <code>uvicorn backend.api:app --reload</code> running?
        </p>
      )}

      {!error && !data && <p className="muted">Loading&hellip;</p>}

      {data && (
        <table>
          <thead>
            <tr>
              <th>Family</th>
              {data.targets.map((t) => (
                <th key={t}>{short(t)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.families.map((fam) => (
              <tr key={fam} className={fam === "TOTAL" ? "total" : ""}>
                <td className="fam">{fam}</td>
                {data.targets.map((t) => {
                  const v = data.asr[t]?.[fam] ?? 0;
                  const isSel = selected?.target === t && selected?.family === fam;
                  return (
                    <td
                      key={t}
                      className={`cell ${isSel ? "sel" : ""}`}
                      style={{ background: asrColor(v) }}
                      onClick={() => openCell(t, fam)}
                    >
                      {(v * 100).toFixed(0)}%
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {renderDetail()}
    </main>
  );
}
