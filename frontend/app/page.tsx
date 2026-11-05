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

type JudgeQuality = {
  tpr: number;
  tnr: number;
  precision: number;
  accuracy: number;
  misses: { name: string; note: string; kind: string }[];
};

type LlmJudgeRow = {
  key: string;
  label: string;
  tpr: number;
  tnr: number;
  precision: number;
  misses: string[];
};

type LlmJudgeData = { judge: string | null; rows: LlmJudgeRow[] };

type Outbound = { recipient: string; body: string; encoding?: string | null };

type AgentSample = {
  leaks: number;
  trials: number;
  blocks: number;
  encodings: string[];
  exfiltration: Outbound[];
  blocked: Outbound[];
};

type AgentData = {
  targets: string[];
  scenarios: string[];
  rate: Record<string, Record<string, number>>;
  asr: Record<string, number>;
  trials: Record<string, number>;
  defense: Record<string, string>;
  samples: Record<string, Record<string, AgentSample>>;
  canary: string;
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
  const [tab, setTab] = useState<"chat" | "agents">("chat");

  // chat tab
  const [data, setData] = useState<CompareData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<{ target: string; family: string } | null>(null);
  const [runs, setRuns] = useState<Record<string, RunDetail>>({}); // cache by run id
  const [judge, setJudge] = useState<JudgeQuality | null>(null);
  const [judgeLlm, setJudgeLlm] = useState<LlmJudgeData | null>(null);

  // agents tab
  const [agents, setAgents] = useState<AgentData | null>(null);
  const [agentSel, setAgentSel] = useState<{ target: string; scenario: string } | null>(null);

  useEffect(() => {
    fetch(`${API}/api/compare`)
      .then((r) => r.json())
      .then(setData)
      .catch((e) => setError(String(e)));
    fetch(`${API}/api/judge`)
      .then((r) => r.json())
      .then(setJudge)
      .catch(() => {}); // non-fatal: the matrix still renders without it
    fetch(`${API}/api/judge-llm`)
      .then((r) => r.json())
      .then((d: LlmJudgeData) => setJudgeLlm(d && d.rows?.length ? d : null))
      .catch(() => {}); // non-fatal: panel hidden until the validation run exists
    fetch(`${API}/api/agents`)
      .then((r) => r.json())
      .then(setAgents)
      .catch(() => {}); // non-fatal: chat tab still works
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

  function renderChat() {
    return (
      <>
        <p className="sub">
          Attack Success Rate by family and model &mdash; lower is safer. Each cell is the
          share of injection attacks that leaked the canary. <strong>Click a cell</strong> to
          read the transcripts.
        </p>

        {judge && (
          <div
            className="judge"
            title="The scorer itself, validated against hand-labeled cases"
          >
            <span className="judge-label">Judge validated</span>
            <span className="stat">
              <b>{(judge.tpr * 100).toFixed(0)}%</b> TPR
            </span>
            <span className="stat">
              <b>{(judge.tnr * 100).toFixed(0)}%</b> TNR
            </span>
            <span className="stat">
              <b>{(judge.precision * 100).toFixed(0)}%</b> precision
            </span>
            <span className="note">
              no false positives + known blind spots (
              {judge.misses.map((m) => m.name.replace("gap-", "")).join(", ")}) &rArr; reported
              ASR is a conservative lower bound
            </span>
          </div>
        )}

        {judgeLlm && judgeLlm.rows.length > 0 && (
          <div className="judgev2">
            <div className="judgev2-head">
              <span className="judge-label">Judge v2 &mdash; validated LLM-judge</span>
              <span className="note">
                The deterministic scorer misses free-form obfuscation (leetspeak, Morse). A
                second-tier LLM-judge is <em>itself</em> validated before being trusted &mdash; a
                false positive would overcount ASR. Their <strong>union</strong> lifts recall
                while precision stays 100%, so the reported ASR is still a conservative lower
                bound.
              </span>
            </div>
            <table className="mini">
              <thead>
                <tr>
                  <th>Judge</th>
                  <th>TPR</th>
                  <th>TNR</th>
                  <th>Precision</th>
                  <th>Misses</th>
                </tr>
              </thead>
              <tbody>
                {judgeLlm.rows.map((r) => (
                  <tr key={r.key} className={r.key === "union" ? "total" : ""}>
                    <td className="fam">{r.label}</td>
                    <td>{(r.tpr * 100).toFixed(0)}%</td>
                    <td>{(r.tnr * 100).toFixed(0)}%</td>
                    <td>{(r.precision * 100).toFixed(0)}%</td>
                    <td className="miss">{r.misses.length ? r.misses.join(", ") : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

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
      </>
    );
  }

  function renderAgentDetail() {
    if (!agentSel || !agents) return null;
    const s = agents.samples[agentSel.target]?.[agentSel.scenario];
    if (!s) return null;
    const leaked = s.leaks > 0;
    const blocked = !leaked && s.blocks > 0;
    const cls = leaked ? "leak" : blocked ? "blocked" : "held";
    const badgeCls = leaked ? "bad" : blocked ? "warn" : "good";
    const badgeText = leaked
      ? `${s.leaks}/${s.trials} leaked · ${s.encodings.join(", ")}`
      : blocked
      ? `${s.blocks}/${s.trials} blocked by guard`
      : `held · 0/${s.trials}`;
    const shown: Outbound[] = leaked ? s.exfiltration : blocked ? s.blocked : [];
    return (
      <section className="detail">
        <div className="detail-head">
          <h2>
            {short(agentSel.target)} <span className="dot">·</span> {agentSel.scenario}
          </h2>
          <button className="close" onClick={() => setAgentSel(null)}>
            ✕ close
          </button>
        </div>
        <article className={`card ${cls}`}>
          <div className="card-head">
            <span className="tech">{agentSel.scenario}</span>
            <span className={`badge ${badgeCls}`}>{badgeText}</span>
          </div>
          {blocked && (
            <p className="muted">
              The injection still fooled the model into calling <code>send_report</code> &mdash;
              the egress guard stopped the secret at the tool boundary.
            </p>
          )}
          {shown.length > 0 ? (
            shown.map((ex, i) => (
              <div key={i}>
                <pre className="line prompt">
                  <span className="who">to</span>
                  {ex.recipient}
                </pre>
                <pre className="line resp">
                  <span className="who">{blocked ? "blocked" : "body"}</span>
                  {highlight(ex.body, agents.canary)}
                </pre>
              </div>
            ))
          ) : (
            <p className="muted">The agent did not exfiltrate the secret in any trial.</p>
          )}
        </article>
      </section>
    );
  }

  function renderAgents() {
    return (
      <>
        <p className="sub">
          A tool-using agent with the <strong>lethal trifecta</strong> &mdash; private notes,
          an untrusted web page, and an email tool. Each cell is the share of trials where an
          injection hidden in the page made the agent email the secret out.{" "}
          <strong>Click a cell</strong> to see the exfiltration.
        </p>

        <div className="judge trifecta" title="Lethal trifecta: private data + untrusted content + exfil channel">
          <span className="judge-label">Lethal trifecta</span>
          <span className="note">
            private data + untrusted content + exfil channel. Same leak judge as the chat
            benchmark, so an agent that encodes the secret before sending is still caught.
          </span>
        </div>

        {!agents && <p className="muted">Loading&hellip;</p>}

        {agents && agents.targets.length === 0 && (
          <p className="muted">
            No agent runs yet. Run{" "}
            <code>python -m scripts.run_agent_benchmark --model llama3.1:8b --trials 5</code>.
          </p>
        )}

        {agents && agents.targets.length > 0 && (
          <table>
            <thead>
              <tr>
                <th>Injection</th>
                {agents.targets.map((t) => (
                  <th key={t}>{short(t)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {agents.scenarios.map((sc) => (
                <tr key={sc}>
                  <td className="fam">{sc}</td>
                  {agents.targets.map((t) => {
                    const v = agents.rate[t]?.[sc] ?? 0;
                    const isSel = agentSel?.target === t && agentSel?.scenario === sc;
                    return (
                      <td
                        key={t}
                        className={`cell ${isSel ? "sel" : ""}`}
                        style={{ background: asrColor(v) }}
                        onClick={() => setAgentSel({ target: t, scenario: sc })}
                      >
                        {(v * 100).toFixed(0)}%
                      </td>
                    );
                  })}
                </tr>
              ))}
              <tr className="total">
                <td className="fam">Agent-ASR</td>
                {agents.targets.map((t) => (
                  <td key={t} style={{ background: asrColor(agents.asr[t] ?? 0) }}>
                    {((agents.asr[t] ?? 0) * 100).toFixed(0)}%
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        )}

        {renderAgentDetail()}
      </>
    );
  }

  return (
    <main className="wrap">
      <h1>InjectBench</h1>

      <div className="tabs">
        <button className={tab === "chat" ? "tab on" : "tab"} onClick={() => setTab("chat")}>
          Chat models
        </button>
        <button className={tab === "agents" ? "tab on" : "tab"} onClick={() => setTab("agents")}>
          Agents
        </button>
      </div>

      {tab === "chat" ? renderChat() : renderAgents()}
    </main>
  );
}
