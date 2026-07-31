"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import { Term } from "../lib/glossary";
import { actionGlyph, actionLabel, api, formatNumber, groupEvents } from "../lib/replay";
import type { ArmSnapshot, FairnessRow, Recording } from "../types";
import { TransformerGrid } from "./transformer-grid";

const Network3D = dynamic(
  () => import("./network-3d").then((module) => module.Network3D),
  { ssr: false, loading: () => <div className="twin-loading"><i /><span>Building spatial network</span></div> },
);

type Props = {
  recording: Recording;
  onStory?: () => void;
};

function PairMetric({ label, baseline, vidyut, unit, lower = true, digits = 1 }: { label: string; baseline: number; vidyut: number; unit: string; lower?: boolean; digits?: number }) {
  const improved = lower ? vidyut <= baseline : vidyut >= baseline;
  return (
    <article className="pair-metric">
      <span>{label}</span>
      <div><small>Baseline</small><strong>{formatNumber(baseline, digits)}<i>{unit}</i></strong></div>
      <div className={improved ? "improved" : "degraded"}><small>Vidyut</small><strong>{formatNumber(vidyut, digits)}<i>{unit}</i></strong></div>
    </article>
  );
}

function HomeDots({ darkHomes, total = 70 }: { darkHomes: number; total?: number }) {
  const cells = 14;
  const dark = Math.ceil((darkHomes / total) * cells);
  return <div className="home-dots" aria-label={`${darkHomes} of approximately ${total} homes dark`}>{Array.from({ length: cells }, (_, index) => <i key={index} className={index < dark ? "dark" : "lit"} />)}</div>;
}

export function ReplayDashboard({ recording, onStory }: Props) {
  const [tick, setTick] = useState(65);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(2);
  const [selectedDt, setSelectedDt] = useState("F1-DT17");
  const [networkView, setNetworkView] = useState<"grid" | "spatial">("grid");
  const [spatialArm, setSpatialArm] = useState<"baseline" | "vidyut">("vidyut");
  const [fairness, setFairness] = useState<FairnessRow[]>([]);
  const frame = recording.ticks[Math.min(tick, recording.ticks.length - 1)];
  const baseline = frame.arms.baseline;
  const vidyut = frame.arms.vidyut;
  const baselineDt = baseline.dts.find((dt) => dt.id === selectedDt) ?? baseline.dts[0];
  const vidyutDt = vidyut.dts.find((dt) => dt.id === selectedDt) ?? vidyut.dts[0];
  const selectedEvents = vidyut.events.filter((event) => event.target === selectedDt);
  const activeTargets = new Set(vidyut.events.map((event) => event.target));
  const groupedActions = groupEvents(vidyut.events);

  const eventTicks = useMemo(() => {
    const markers = new Set<number>();
    for (const item of recording.ticks) {
      if (item.arms.baseline.events.length || item.arms.vidyut.events.some((event) => [1, 3].includes(event.tier))) markers.add(item.t);
      if (item.arms.baseline.metrics.max_trafo_loading_pct >= 100 && !markers.size) markers.add(item.t);
    }
    return [...markers];
  }, [recording]);

  const cumulative = useMemo(() => {
    const events = recording.ticks.slice(0, tick + 1).flatMap((item) => item.arms.vidyut.events);
    return {
      total: events.length,
      voluntary: events.filter((event) => event.tier === 0).length,
      scheduled: events.filter((event) => event.tier === 1).length,
      targeted: events.filter((event) => event.tier === 2).length,
      lastResort: events.filter((event) => event.tier === 3).length,
    };
  }, [recording, tick]);

  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(() => {
      setTick((value) => {
        if (value >= recording.ticks.length - 1) {
          setPlaying(false);
          return value;
        }
        return value + 1;
      });
    }, 1000 / speed);
    return () => window.clearInterval(timer);
  }, [playing, recording.ticks.length, speed]);

  useEffect(() => {
    api<{ households: FairnessRow[] }>("/api/fairness/leaderboard?limit=6")
      .then((response) => setFairness(response.households))
      .catch(() => setFairness([]));
  }, []);

  function changeTick(value: number) {
    setTick(value);
    setPlaying(false);
  }

  return (
    <section className="replay-dashboard">
      <div className="replay-heading">
        <div><span className="section-code">INTERACTIVE REPLAY</span><h1>See exactly when the outcomes diverge.</h1><p>Drag the recorded day or press play. The network, localities, decisions and fairness ledger all move to the same 15-minute interval.</p></div>
        <div className="replay-heading-actions">{onStory && <button type="button" className="secondary-button" onClick={onStory}>↺ Watch story</button>}<span>Recorded · seed {recording.meta.seed}</span></div>
      </div>

      <div className="metric-ribbon">
        <PairMetric label="Homes dark now" baseline={baseline.metrics.homes_dark} vidyut={vidyut.metrics.homes_dark} unit="homes" digits={0} />
        <PairMetric label="Unserved so far" baseline={baseline.metrics.unserved_kwh} vidyut={vidyut.metrics.unserved_kwh} unit="kWh" />
        <PairMetric label="Peak transformer" baseline={baseline.metrics.max_trafo_loading_pct} vidyut={vidyut.metrics.max_trafo_loading_pct} unit="%" />
        <PairMetric label="Critical uptime" baseline={baseline.metrics.critical_uptime_pct} vidyut={vidyut.metrics.critical_uptime_pct} unit="%" lower={false} digits={2} />
      </div>

      <div className="network-view-bar">
        <p>
          Every block is one <Term k="transformer">transformer</Term> feeding about seventy homes.
          Its height and colour show how close it is to its <Term k="loading">limit</Term>.
        </p>
        <div className="view-toggle" role="group" aria-label="Network view">
          <button type="button" className={networkView === "grid" ? "active" : ""} onClick={() => setNetworkView("grid")} aria-pressed={networkView === "grid"}>Grid</button>
          <button type="button" className={networkView === "spatial" ? "active" : ""} onClick={() => setNetworkView("spatial")} aria-pressed={networkView === "spatial"}>3D</button>
        </div>
        {networkView === "spatial" && <div className="arm-switch" role="group" aria-label="Spatial strategy"><button type="button" className={spatialArm === "baseline" ? "active danger" : ""} onClick={() => setSpatialArm("baseline")}>Baseline</button><button type="button" className={spatialArm === "vidyut" ? "active" : ""} onClick={() => setSpatialArm("vidyut")}>Vidyut</button></div>}
      </div>

      {networkView === "grid" ? <div className="network-compare">
        {([["baseline", baseline, "Baseline", undefined], ["vidyut", vidyut, "Vidyut", activeTargets]] as const).map(([key, snapshot, title, targets]) => (
          <article className={`network-arm ${key}-arm`} key={key}>
            <div className="arm-heading"><span><i />{title}</span><strong>{formatNumber((snapshot as ArmSnapshot).metrics.max_trafo_loading_pct)}% <small>max loading</small></strong></div>
            <TransformerGrid snapshot={snapshot as ArmSnapshot} selectedDt={selectedDt} onSelect={setSelectedDt} activeTargets={targets} />
          </article>
        ))}
      </div> : <div className="network-compare spatial-single"><article className={`network-arm ${spatialArm}-arm`}><div className="arm-heading"><span><i />{spatialArm === "baseline" ? "Baseline" : "Vidyut"} spatial network</span><strong>{formatNumber(frame.arms[spatialArm].metrics.max_trafo_loading_pct)}% <small>max loading</small></strong></div><Network3D snapshot={frame.arms[spatialArm]} label={`${spatialArm} at ${frame.clock}`} selectedDt={selectedDt} onSelect={setSelectedDt} activeTargets={spatialArm === "vidyut" ? activeTargets : new Set()} /></article></div>}

      <section className="selected-locality">
        <div className="locality-title"><span className="section-code">SELECTED LOCALITY</span><h2>{selectedDt}</h2><p>Each light represents roughly five homes on this transformer.</p></div>
        <div className="locality-arm baseline">
          <div><span>Baseline</span><strong>{formatNumber(baselineDt.loading_pct)}%</strong></div>
          <HomeDots darkHomes={baselineDt.households_dark} />
          <p>{baselineDt.energized ? `${baselineDt.households_dark} homes dark` : "Transformer off · entire locality dark"}</p>
        </div>
        <div className="locality-divider">VS</div>
        <div className="locality-arm vidyut">
          <div><span>Vidyut</span><strong>{formatNumber(vidyutDt.loading_pct)}%</strong></div>
          <HomeDots darkHomes={vidyutDt.households_dark} />
          <p>{vidyutDt.energized ? `${vidyutDt.households_dark} homes dark` : "Transformer off"}</p>
        </div>
        <div className="locality-actions">
          <span>Actions at {frame.clock}</span>
          {selectedEvents.length ? selectedEvents.slice(0, 3).map((event, index) => <div key={`${event.action}-${index}`}><b>{actionGlyph(event.action)}</b><p><strong>{actionLabel(event.action)}</strong><small>{formatNumber(event.kw)} kW · {event.households} households</small></p></div>) : <p>No new targeted action on this transformer in this interval.</p>}
        </div>
      </section>

      <div className="operational-grid">
        <section className="action-feed">
          <div className="panel-heading"><div><span className="section-code">CONTROLLER ACTIONS</span><h2>{frame.clock}</h2></div><span>{vidyut.events.length} decisions</span></div>
          {groupedActions.length ? <div className="action-groups">{groupedActions.slice(0, 6).map((action) => <article key={action.action}><b>{actionGlyph(action.action)}</b><div><strong>{actionLabel(action.action)}</strong><span>{action.count} locations · {formatNumber(action.kw)} kW</span></div><em>{action.households}</em></article>)}</div> : <div className="quiet-state"><i>✓</i><p>No intervention required at this interval.<span>The controller is monitoring forecasts and safe limits.</span></p></div>}
        </section>

        <section className="fairness-panel">
          <div className="panel-heading"><div><span className="section-code">FAIRNESS & SAFETY</span><h2>Burden ledger</h2></div><span>{cumulative.total} actions so far</span></div>
          <div className="fairness-live">
            <div><span>Burden inequality</span><strong>{formatNumber(vidyut.metrics.gini, 3)}</strong><small>live Gini</small></div>
            <div><span>Critical services</span><strong>{formatNumber(vidyut.metrics.critical_uptime_pct, 2)}%</strong><small>uptime</small></div>
          </div>
          <div className="tier-track"><i style={{ flex: Math.max(cumulative.voluntary, 1) }} /><i style={{ flex: Math.max(cumulative.scheduled, 1) }} /><i style={{ flex: Math.max(cumulative.targeted, 1) }} /><i style={{ flex: Math.max(cumulative.lastResort, 1) }} /></div>
          <div className="tier-legend"><span>T0 voluntary {cumulative.voluntary}</span><span>T1 shifted {cumulative.scheduled}</span><span>T2 targeted {cumulative.targeted}</span><span>T3 last resort {cumulative.lastResort}</span></div>
          {fairness.length > 0 && <div className="ledger-preview"><span>Highest carried burden in persisted ledger</span>{fairness.slice(0, 3).map((row) => <div key={row.household_id}><code>{row.household_id}</code><span>{row.dt_id}</span><strong>{formatNumber(row.cumulative_debt_min, 0)} min</strong></div>)}</div>}
        </section>
      </div>

      <section className="timeline-panel">
        <div className="timeline-head">
          <div className="playback-controls">
            <button type="button" className="play-button" onClick={() => { if (tick === recording.ticks.length - 1) setTick(0); setPlaying((value) => !value); }} aria-label={playing ? "Pause replay" : "Play replay"}>{playing ? "Ⅱ" : "▶"}</button>
            <button type="button" onClick={() => changeTick(Math.max(0, tick - 1))} aria-label="Previous interval">←</button>
            <button type="button" onClick={() => changeTick(Math.min(recording.ticks.length - 1, tick + 1))} aria-label="Next interval">→</button>
          </div>
          <div className="current-time"><strong>{frame.clock}</strong><span>Tick {tick + 1} of {recording.ticks.length}</span></div>
          <div className="speed-controls" aria-label="Playback speed">{[1, 2, 4].map((value) => <button type="button" className={speed === value ? "active" : ""} onClick={() => setSpeed(value)} key={value}>{value}×</button>)}</div>
        </div>

        <div className="timeline-chart" aria-hidden="true">
          {recording.ticks.map((item) => <i key={item.t} className={`${item.t <= tick ? "elapsed" : ""} ${item.arms.baseline.metrics.homes_dark ? "outage" : ""}`} style={{ height: `${Math.max(8, item.arms.baseline.metrics.max_trafo_loading_pct / 1.35)}%` }} />)}
        </div>
        <div className="timeline-range-wrap">
          {eventTicks.map((marker) => <button type="button" className="timeline-marker" key={marker} style={{ left: `${marker / (recording.ticks.length - 1) * 100}%` }} onClick={() => changeTick(marker)} aria-label={`Jump to event at ${recording.ticks[marker].clock}`} />)}
          <input type="range" min="0" max={recording.ticks.length - 1} value={tick} onChange={(event) => changeTick(Number(event.target.value))} aria-label="Replay time" />
        </div>
        <div className="timeline-labels"><span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>24:00</span></div>
      </section>

      <section className="day-outcome">
        <div><span className="section-code">END-OF-DAY IMPACT</span><h2>The whole outcome, without hiding the interventions.</h2></div>
        <PairMetric label="Homes-dark minutes" baseline={recording.summary.arms.baseline.homes_dark_minutes} vidyut={recording.summary.arms.vidyut.homes_dark_minutes} unit="min" digits={0} />
        <PairMetric label="Unserved energy" baseline={recording.summary.arms.baseline.unserved_kwh} vidyut={recording.summary.arms.vidyut.unserved_kwh} unit="kWh" />
        <PairMetric label="Critical uptime" baseline={recording.summary.arms.baseline.critical_uptime_pct} vidyut={recording.summary.arms.vidyut.critical_uptime_pct} unit="%" lower={false} digits={2} />
      </section>
    </section>
  );
}
