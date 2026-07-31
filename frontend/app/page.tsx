"use client";

import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Summary = {
  arms: { baseline: Record<string, number>; vidyut: Record<string, number> };
};

type Flexibility = {
  registered: {
    capacity_kw: number;
    households: number;
    devices: number;
    capacity_by_kind_kw: Record<string, number>;
    source: string;
  };
  available: { profile_kw: number[]; peak_kw: number; energy_kwh: number };
  realised: { reduction_kwh: number; source: string };
};

type Estimate = {
  ready: boolean;
  source: string;
  confidence: string;
  coverage_pct: number;
  estimated_peak_kw: number;
  actionable_peak_kw: number | null;
  actionable_profile_kw: number[] | null;
};

type Verification = {
  source: string;
  confidence: string;
  baseline_average_kw: number;
  observed_average_kw: number;
  realised_reduction_kw: number;
  realised_reduction_kwh: number;
  performance_pct: number | null;
};

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

function number(value: number | null | undefined, digits = 1) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat("en-IN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

function label(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function Source({ value }: { value: string }) {
  return <span className={`source source-${value}`}>{value}</span>;
}

function Bars({ values }: { values: number[] }) {
  const max = Math.max(...values, 1);
  return (
    <div className="bars" aria-label="15-minute availability profile">
      {values.map((value, index) => (
        <i
          key={`${index}-${value}`}
          style={{ height: `${Math.max(5, (value / max) * 100)}%` }}
          title={`Interval ${index + 1}: ${number(value)} kW`}
        />
      ))}
    </div>
  );
}

export default function Home() {
  const [online, setOnline] = useState<boolean | null>(null);
  const [database, setDatabase] = useState(false);
  const [scenario, setScenario] = useState("heatwave");
  const [seed, setSeed] = useState(42);
  const [ticks, setTicks] = useState(12);
  const [status, setStatus] = useState("not started");
  const [runId, setRunId] = useState<string | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [flexibility, setFlexibility] = useState<Flexibility | null>(null);
  const [estimate, setEstimate] = useState<Estimate | null>(null);
  const [verification, setVerification] = useState<Verification | null>(null);
  const [busy, setBusy] = useState(false);
  const [labBusy, setLabBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([
      api<{ status: string; database: { reachable: boolean } }>("/api/health"),
      api<{ ready: boolean }>("/api/observability/status"),
    ])
      .then(([health, observability]) => {
        if (!active) return;
        setOnline(health.status === "ok" && observability.ready);
        setDatabase(health.database.reachable);
      })
      .catch(() => active && setOnline(false));
    return () => {
      active = false;
    };
  }, []);

  async function waitForRun(id: string) {
    for (let attempt = 0; attempt < 240; attempt += 1) {
      const result = await api<{ status: string; error?: string }>(`/api/runs/${id}`);
      setStatus(result.status);
      if (result.status === "ready") return;
      if (result.status === "failed") throw new Error(result.error ?? "Simulation failed");
      await new Promise((resolve) => window.setTimeout(resolve, 500));
    }
    throw new Error("The simulation did not finish within two minutes");
  }

  async function runSimulation() {
    setBusy(true);
    setError(null);
    setSummary(null);
    setFlexibility(null);
    try {
      const created = await api<{ run_id: string; status: string }>("/api/runs", {
        method: "POST",
        body: JSON.stringify({ scenario, seed, ticks, carry_debt: false }),
      });
      setRunId(created.run_id);
      setStatus(created.status);
      await waitForRun(created.run_id);
      const [nextSummary, nextFlexibility] = await Promise.all([
        api<Summary>(`/api/runs/${created.run_id}/summary`),
        api<Flexibility>(`/api/runs/${created.run_id}/flexibility`),
      ]);
      setSummary(nextSummary);
      setFlexibility(nextFlexibility);
    } catch (caught) {
      setStatus("failed");
      setError(caught instanceof Error ? caught.message : "Could not run simulation");
    } finally {
      setBusy(false);
    }
  }

  async function runEstimate() {
    setLabBusy("estimate");
    setError(null);
    try {
      const ambient = Array.from({ length: 7 }, (_, day) =>
        [21, 22, 24, 27, 30, 32, 28, 24].map((value) => value + day),
      );
      const aggregate = ambient.map((day) =>
        day.map((temperature) => 8 + 1.2 * Math.max(temperature - 24, 0)),
      );
      setEstimate(
        await api<Estimate>("/api/observability/flexibility/estimate", {
          method: "POST",
          body: JSON.stringify({
            aggregate_kw: aggregate,
            ambient_c: ambient,
            registered_capacity_kw: 5,
          }),
        }),
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Estimate failed");
    } finally {
      setLabBusy(null);
    }
  }

  async function runVerification() {
    setLabBusy("verify");
    setError(null);
    try {
      setVerification(
        await api<Verification>("/api/observability/events/verify", {
          method: "POST",
          body: JSON.stringify({
            history_kw: [100, 110, 120, 130, 140].map((value) => Array(8).fill(value)),
            observed_kw: [125, 125, 125, 125, 105, 105, 125, 125],
            event_start_index: 4,
            event_end_index: 6,
            committed_reduction_kw: 20,
          }),
        }),
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Verification failed");
    } finally {
      setLabBusy(null);
    }
  }

  const metrics = [
    ["unserved_kwh", "Unserved energy", "kWh"],
    ["homes_dark_minutes", "Homes-dark time", "min"],
    ["critical_uptime_pct", "Critical uptime", "%"],
    ["max_trafo_loading_pct", "Max transformer load", "%"],
  ];

  return (
    <main className="shell">
      <header>
        <div className="brand"><b>V</b><span><small>VIDYUT / BACKEND EXPLORER</small><strong>See the grid think.</strong></span></div>
        <div className={`health ${online === true ? "online" : online === false ? "offline" : "checking"}`}>
          <i />
          <span><b>{online === true ? "Backend online" : online === false ? "Backend offline" : "Checking backend"}</b><small>{API_URL.replace(/^https?:\/\//, "")}</small></span>
        </div>
      </header>

      <nav aria-label="Backend flow">
        <span>01 SIMULATE</span><b>→</b><span>02 BALANCE</span><b>→</b><span>03 OBSERVE</span><b>→</b><span>04 VERIFY</span>
      </nav>

      {online === false && <div className="alert">The frontend cannot reach {API_URL}. Start the backend and refresh.</div>}
      {error && <div className="alert">{error}</div>}

      <section className="hero">
        <div>
          <p className="kicker">BASIC DEMONSTRATOR · NOT THE FINAL OPERATOR UI</p>
          <h1>Run one day.<br />Inspect every claim.</h1>
          <p className="intro">This screen calls the real backend. Compare the uncontrolled baseline with Vidyut, inspect known controllable capacity, and test the new estimate and verification methods.</p>
          <div className="legend"><Source value="registered" /><span>known capability</span><Source value="estimated" /><span>AMI + weather</span><Source value="verified" /><span>event result</span></div>
        </div>

        <aside className="run-card">
          <div className="card-title"><span><small>CONTROL 01</small><b>Run simulation</b></span><em>{status}</em></div>
          <div className="fields">
            <label>Scenario<select value={scenario} onChange={(event) => setScenario(event.target.value)} disabled={busy}><option value="normal">Normal</option><option value="heatwave">Heatwave</option><option value="ev_surge">EV surge</option></select></label>
            <label>Seed<input type="number" value={seed} onChange={(event) => setSeed(Number(event.target.value))} disabled={busy} /></label>
            <label>15-min ticks<input type="number" min="3" max="96" value={ticks} onChange={(event) => setTicks(Math.max(3, Math.min(96, Number(event.target.value))))} disabled={busy} /></label>
          </div>
          <button className="primary" onClick={runSimulation} disabled={busy || online !== true}>{busy ? "Working…" : "Run backend simulation"}</button>
          <p>12 ticks represent three hours. Use 96 for a complete day.</p>
        </aside>
      </section>

      <section className="block">
        <div className="heading"><span><small>RESULT 02</small><h2>Baseline vs Vidyut</h2></span><p>Same network, population, seed and demand. Only the controller changes.</p></div>
        {!summary ? <div className="empty">Run a simulation to populate this comparison.</div> : (
          <>
            <div className="metric-table">
              <div className="metric-head"><span>OUTCOME</span><span>BASELINE</span><span>VIDYUT</span><span>CHANGE</span></div>
              {metrics.map(([key, name, unit]) => {
                const baseline = summary.arms.baseline[key];
                const vidyut = summary.arms.vidyut[key];
                const delta = vidyut - baseline;
                const positive = key === "critical_uptime_pct" ? delta >= 0 : delta <= 0;
                return <div className="metric-row" key={key}><strong>{name}<small>{unit}</small></strong><span>{number(baseline)}</span><span>{number(vidyut)}</span><span className={positive ? "good" : "bad"}>{delta > 0 ? "+" : ""}{number(delta)}</span></div>;
              })}
            </div>
            <div className="run-meta">Run ID <code>{runId}</code>{runId && <a href={`${API_URL}/api/runs/${runId}/report`} target="_blank" rel="noreferrer">Open audit PDF ↗</a>}</div>
          </>
        )}
      </section>

      <section className="block">
        <div className="heading"><span><small>RESULT 03</small><h2>Registered flexibility</h2></span><p>Known controllable devices. No appliance guessing.</p></div>
        {!flexibility ? <div className="empty">The flexibility envelope appears after a run.</div> : (
          <div className="flex-grid">
            <article className="capacity"><Source value={flexibility.registered.source} /><strong>{number(flexibility.registered.capacity_kw, 0)}<small> kW</small></strong><p>Controllable nameplate capacity</p><div><span><b>{flexibility.registered.households}</b> households</span><span><b>{flexibility.registered.devices}</b> devices</span></div></article>
            <article><p className="kicker">CAPACITY BY ASSET</p><div className="asset-list">{Object.entries(flexibility.registered.capacity_by_kind_kw).map(([kind, value]) => <div key={kind}><span>{label(kind)}</span><i><b style={{ width: `${Math.max(2, value / flexibility.registered.capacity_kw * 100)}%` }} /></i><em>{number(value, 0)} kW</em></div>)}</div></article>
            <article><div className="profile-title"><span><p className="kicker">ACTIVE AVAILABILITY</p><b>{number(flexibility.available.peak_kw)} kW peak</b></span><strong>{number(flexibility.available.energy_kwh)} kWh</strong></div><Bars values={flexibility.available.profile_kw} /><p className="hint">One bar per 15-minute interval.</p></article>
          </div>
        )}
      </section>

      <section className="block lab">
        <div className="heading"><span><small>LAB 04</small><h2>Observability methods</h2></span><p>Known sample inputs make each calculation easy to inspect.</p></div>
        <div className="lab-grid">
          <article className="lab-card">
            <p className="kicker">A · AMI + WEATHER</p><h3>Estimate opportunity</h3><p>Seven comparable days, aggregate readings, ambient temperature and a 5 kW registered cap.</p>
            <button className="secondary" onClick={runEstimate} disabled={labBusy !== null || online !== true}>{labBusy === "estimate" ? "Estimating…" : "Run sample estimate"}</button>
            {estimate && <div className="lab-result"><div><Source value={estimate.source} /><span>{estimate.confidence} confidence</span></div><strong>{number(estimate.estimated_peak_kw, 2)} <i>→</i> {number(estimate.actionable_peak_kw, 2)} kW</strong><small>estimated → actionable after registered cap</small><Bars values={estimate.actionable_profile_kw ?? []} /><p>{number(estimate.coverage_pct)}% joint data coverage</p></div>}
          </article>
          <article className="lab-card dark">
            <p className="kicker">B · EVENT M&amp;V</p><h3>Verify actual response</h3><p>Five comparable days establish a high-4-of-5 baseline against a 20 kW commitment.</p>
            <button className="light" onClick={runVerification} disabled={labBusy !== null || online !== true}>{labBusy === "verify" ? "Verifying…" : "Run sample verification"}</button>
            {verification && <div className="lab-result"><div><Source value={verification.source} /><span>{verification.confidence} confidence</span></div><strong>{number(verification.realised_reduction_kw)} kW</strong><small>{number(verification.realised_reduction_kwh)} kWh verified · {number(verification.performance_pct)}% performance</small><dl><div><dt>Baseline</dt><dd>{number(verification.baseline_average_kw)} kW</dd></div><div><dt>Observed</dt><dd>{number(verification.observed_average_kw)} kW</dd></div></dl></div>}
          </article>
        </div>
      </section>

      <footer><span>VIDYUT · BASIC BACKEND EXPLORER</span><span>Database {database ? "connected" : "not connected"} · Observability {online ? "ready" : "unavailable"}</span></footer>
    </main>
  );
}
