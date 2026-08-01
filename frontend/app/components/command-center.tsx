"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import { Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Recording, ScenarioName } from "../types";
import { actionGlyph, actionLabel, formatNumber, groupEvents } from "../lib/replay";
import { AiExplainer } from "./ai-explainer";

const Network3D = dynamic(
  () => import("./network-3d").then((module) => module.Network3D),
  { ssr: false, loading: () => <div className="twin-loading"><i /><span>Building spatial network</span></div> },
);

type CommandCenterProps = {
  recording: Recording;
  scenario: ScenarioName;
  online: boolean;
  source: { kind: "demo" } | { kind: "generated"; runId: string };
  onOpenReplay: () => void;
  onOpenSimulation: () => void;
};

function findRiskTick(recording: Recording) {
  const riskIndex = recording.ticks.findIndex((frame) => frame.arms.baseline.metrics.max_trafo_loading_pct >= 100);
  return riskIndex >= 0 ? riskIndex : Math.max(0, Math.min(65, recording.ticks.length - 1));
}

export function CommandCenter({ recording, scenario, online, source, onOpenReplay, onOpenSimulation }: CommandCenterProps) {
  const [tick, setTick] = useState(() => findRiskTick(recording));
  const [playing, setPlaying] = useState(false);
  const [arm, setArm] = useState<"vidyut" | "baseline">("vidyut");
  const [selectedDt, setSelectedDt] = useState("F1-DT17");
  const frame = recording.ticks[tick];
  const snapshot = frame.arms[arm];
  const selected = snapshot.dts.find((dt) => dt.id === selectedDt) ?? snapshot.dts[0];
  const otherSelected = frame.arms[arm === "vidyut" ? "baseline" : "vidyut"].dts.find((dt) => dt.id === selected.id);
  const activeTargets = new Set(frame.arms.vidyut.events.map((event) => event.target));
  const actions = groupEvents(frame.arms.vidyut.events);
  const totals = recording.summary.arms;

  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(() => setTick((current) => {
      if (current >= recording.ticks.length - 1) {
        setPlaying(false);
        return current;
      }
      return current + 1;
    }), 650);
    return () => window.clearInterval(timer);
  }, [playing, recording.ticks.length]);

  const chart = useMemo(() => recording.ticks.map((item) => ({
    tick: item.t,
    clock: item.clock,
    baseline: Number(item.arms.baseline.metrics.max_trafo_loading_pct.toFixed(1)),
    vidyut: Number(item.arms.vidyut.metrics.max_trafo_loading_pct.toFixed(1)),
  })), [recording]);

  const avoided = totals.baseline.homes_dark_minutes - totals.vidyut.homes_dark_minutes;
  const riskState = selected.energized ? selected.loading_pct >= 100 ? "Critical" : selected.loading_pct >= 90 ? "Watch" : "Stable" : "Offline";

  return <main className="command-center">
    <section className="command-titlebar">
      <div><span className="command-code">{source.kind === "generated" ? "YOUR GENERATED SIMULATION" : "AUTO-LOADED DEMO RECORDING"}</span><h1>Distribution command</h1><p>One synchronized view of demand, network state, interventions and their human impact.</p></div>
      <div className="command-title-actions"><span className={`operating-pill ${online ? "online" : ""}`}><i />{online ? "Simulation core connected" : "Recorded replay"}</span><button type="button" onClick={onOpenSimulation}>Run new scenario <b>↗</b></button></div>
    </section>

    <section className={`recording-provenance ${source.kind}`} aria-label="Simulation data source">
      <div className="provenance-mark">{source.kind === "generated" ? "✓" : "D"}</div>
      <div className="provenance-copy">
        <span>{source.kind === "generated" ? "Generated in this session" : "Why data is already visible"}</span>
        <strong>{source.kind === "generated" ? "You are viewing the run you just created." : "This is a pre-recorded demonstration—not live grid data."}</strong>
        <p>{source.kind === "generated" ? "The command center and 3D twin now use the exact frames produced by your Simulation Lab run." : "Vidyut loads one deterministic scenario so the command center is useful on first visit. Run a scenario to replace it with your own result."}</p>
      </div>
      <div className="provenance-meta">
        <span>Scenario<strong>{scenario.replaceAll("_", " ")}</strong></span>
        <span>Seed<strong>{recording.meta.seed}</strong></span>
        <span>Intervals<strong>{recording.ticks.length}</strong></span>
        {source.kind === "generated" && <span>Run ID<strong>{source.runId.slice(0, 8)}</strong></span>}
      </div>
      <button type="button" onClick={source.kind === "generated" ? onOpenReplay : onOpenSimulation}>{source.kind === "generated" ? "Explore this replay →" : "Create my own run →"}</button>
    </section>

    <section className="command-kpis">
      <article><span>Power flow <i>◇</i></span><strong>{snapshot.metrics.converged ? "Converged" : "Attention"}</strong><div><b style={{ width: snapshot.metrics.converged ? "100%" : "12%" }} /></div><small>{snapshot.dts.length} transformer states solved this interval</small></article>
      <article><span>Peak transformer <i>△</i></span><strong className={snapshot.metrics.max_trafo_loading_pct >= 100 ? "warn" : ""}>{formatNumber(snapshot.metrics.max_trafo_loading_pct)}%</strong><div><b style={{ width: `${Math.min(100, snapshot.metrics.max_trafo_loading_pct)}%` }} /></div><small>{snapshot.metrics.max_trafo_loading_pct >= 100 ? "Above equipment rating" : "Within operating range"}</small></article>
      <article><span>Outage burden avoided <i>↗</i></span><strong>{formatNumber(avoided, 0)}</strong><div><b style={{ width: `${Math.min(100, avoided / Math.max(totals.baseline.homes_dark_minutes, 1) * 100)}%` }} /></div><small>homes-dark minutes · full day</small></article>
      <article><span>Critical uptime <i>+</i></span><strong>{formatNumber(snapshot.metrics.critical_uptime_pct, 2)}%</strong><div><b style={{ width: `${snapshot.metrics.critical_uptime_pct}%` }} /></div><small>Protected services remain powered</small></article>
    </section>

    <section className="command-grid">
      <article className="command-panel demand-panel">
        <div className="command-panel-head"><div><span>NETWORK LOADING</span><h2>Demand pressure through the day</h2></div><div className="chart-key"><span><i className="baseline" />Baseline</span><span><i className="vidyut" />Vidyut</span></div></div>
        <div className="demand-chart">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chart} margin={{ top: 12, right: 6, left: -25, bottom: 0 }}>
              <defs><linearGradient id="vidyutArea" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#c9f04d" stopOpacity={.32} /><stop offset="100%" stopColor="#c9f04d" stopOpacity={0} /></linearGradient><linearGradient id="baselineArea" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#ff754c" stopOpacity={.18} /><stop offset="100%" stopColor="#ff754c" stopOpacity={0} /></linearGradient></defs>
              <CartesianGrid vertical={false} stroke="rgba(224,239,230,.08)" />
              <XAxis dataKey="clock" interval={23} tick={{ fill: "#718078", fontSize: 10 }} axisLine={false} tickLine={false} />
              <YAxis domain={[0, 135]} tick={{ fill: "#718078", fontSize: 10 }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ background: "#0d1b16", border: "1px solid rgba(224,239,230,.18)", fontSize: 10 }} labelStyle={{ color: "#c9f04d" }} />
              <ReferenceLine y={100} stroke="#ff754c" strokeDasharray="4 4" label={{ value: "equipment limit", fill: "#ff8d6b", fontSize: 10 }} />
              <ReferenceLine x={frame.clock} stroke="#edf6ef" strokeOpacity={.55} />
              <Area type="monotone" dataKey="baseline" stroke="#ff754c" fill="url(#baselineArea)" strokeWidth={1.4} dot={false} />
              <Area type="monotone" dataKey="vidyut" stroke="#c9f04d" fill="url(#vidyutArea)" strokeWidth={2} dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
        <div className="demand-summary"><div><span>Current interval</span><strong>{frame.clock}</strong></div><div><span>Baseline peak now</span><strong>{formatNumber(frame.arms.baseline.metrics.max_trafo_loading_pct)}%</strong></div><div><span>Vidyut peak now</span><strong>{formatNumber(frame.arms.vidyut.metrics.max_trafo_loading_pct)}%</strong></div></div>
      </article>

      <article className="command-panel twin-panel">
        <div className="command-panel-head"><div><span>SPATIAL DIGITAL TWIN</span><h2>Network topology</h2></div><div className="arm-switch" role="group" aria-label="Network strategy"><button type="button" className={arm === "baseline" ? "active danger" : ""} onClick={() => setArm("baseline")}>Baseline</button><button type="button" className={arm === "vidyut" ? "active" : ""} onClick={() => setArm("vidyut")}>Vidyut</button></div></div>
        <Network3D snapshot={snapshot} label={`${arm === "vidyut" ? "Vidyut" : "Baseline"} network at ${frame.clock}`} selectedDt={selectedDt} onSelect={setSelectedDt} activeTargets={arm === "vidyut" ? activeTargets : new Set()} />
        <div className="asset-strip"><div><span>Selected locality</span><strong>{selected.id}</strong></div><div><span>Loading</span><strong className={selected.loading_pct >= 100 ? "warn" : ""}>{formatNumber(selected.loading_pct)}%</strong></div><div><span>State</span><strong>{riskState}</strong></div><div><span>Homes dark</span><strong>{selected.households_dark}</strong></div><div><span>Other strategy</span><strong>{formatNumber(otherSelected?.loading_pct)}%</strong></div></div>
      </article>

      <aside className="decision-column">
        <section className="command-panel decision-feed">
          <div className="command-panel-head"><div><span>DECISION FEED</span><h2>{frame.clock}</h2></div><b>{frame.arms.vidyut.events.length} NEW</b></div>
          {actions.length ? <div className="decision-list">{actions.slice(0, 5).map((action, index) => <article key={action.action}><i>{actionGlyph(action.action)}</i><div><span>{index === 0 ? "Current response" : "Coordinated action"}</span><strong>{actionLabel(action.action)}</strong><p>{formatNumber(action.kw)} kW across {action.households || action.count} household actions</p></div></article>)}</div> : <div className="monitoring-state"><i>✓</i><strong>No action needed</strong><p>The controller is monitoring forecasts and equipment limits.</p></div>}
          <button className="feed-link" type="button" onClick={onOpenReplay}>Open full decision replay →</button>
        </section>
        <AiExplainer frame={frame} scenario={scenario} transformer={selected} />
      </aside>
    </section>

    <section className="command-timeline">
      <div className="timeline-controls"><button type="button" onClick={() => { if (tick >= recording.ticks.length - 1) setTick(0); setPlaying((value) => !value); }} aria-label={playing ? "Pause replay" : "Play replay"}>{playing ? "Ⅱ" : "▶"}</button><button type="button" onClick={() => { setPlaying(false); setTick(Math.max(0, tick - 1)); }} aria-label="Previous interval">←</button><button type="button" onClick={() => { setPlaying(false); setTick(Math.min(recording.ticks.length - 1, tick + 1)); }} aria-label="Next interval">→</button></div>
      <div className="timeline-clock"><strong>{frame.clock}</strong><span>{scenario.replaceAll("_", " ")} · interval {tick + 1} / {recording.ticks.length}</span></div>
      <div className="command-track"><div className="track-bars">{recording.ticks.map((item) => <i key={item.t} className={`${item.t <= tick ? "elapsed" : ""} ${item.arms.baseline.metrics.homes_dark > 0 ? "outage" : ""}`} style={{ height: `${Math.max(16, item.arms.baseline.metrics.max_trafo_loading_pct / 1.25)}%` }} />)}</div><input type="range" min={0} max={recording.ticks.length - 1} value={tick} onChange={(event) => { setPlaying(false); setTick(Number(event.target.value)); }} aria-label="Recorded day timeline" /></div>
      <div className="timeline-legend"><span><i className="normal" />Normal</span><span><i className="risk" />Overload</span><span><i className="outage" />Outage</span></div>
    </section>
  </main>;
}
