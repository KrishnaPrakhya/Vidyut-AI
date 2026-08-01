"use client";

import dynamic from "next/dynamic";
import { useMemo, useState } from "react";
import type { Recording, RunFlexibility, RunSummary, ScenarioName, TickFrame } from "../types";
import { API_URL, api, formatNumber, titleCase } from "../lib/replay";
import { TransformerGrid } from "./transformer-grid";

const Network3D = dynamic(
  () => import("./network-3d").then((module) => module.Network3D),
  { ssr: false, loading: () => <div className="twin-loading"><i /><span>Building spatial network</span></div> },
);

type SimulationLabProps = {
  online: boolean;
  onOpenCommandCenter: (recording: Recording, runId: string) => void;
};

type EventResponse = {
  total: number;
  events: Array<{ t: number; tier: number; action: string; target: string; kw: number; households: number }>;
};

type NotificationResponse = {
  count: number;
  notifications: Array<{ tick: number; clock: string; event_type: string; households: number; message: string }>;
};

const defaultParams = {
  ami_penetration: 0.72,
  connected_device_penetration: 0.46,
  ev_penetration: 0.12,
  critical_share: 0.03,
  peak_multiplier: 1.35,
};

export function SimulationLab({ online, onOpenCommandCenter }: SimulationLabProps) {
  const [scenario, setScenario] = useState<ScenarioName>("heatwave");
  const [seed, setSeed] = useState(42);
  const [ticks, setTicks] = useState(96);
  const [advanced, setAdvanced] = useState(false);
  const [params, setParams] = useState(defaultParams);
  const [phase, setPhase] = useState("Ready to run");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [summary, setSummary] = useState<RunSummary | null>(null);
  const [flexibility, setFlexibility] = useState<RunFlexibility | null>(null);
  const [events, setEvents] = useState<EventResponse | null>(null);
  const [notifications, setNotifications] = useState<NotificationResponse | null>(null);
  const [dispatchResult, setDispatchResult] = useState<string | null>(null);
  const [dispatchPhase, setDispatchPhase] = useState<"idle" | "accepted" | "delivered" | "failed">("idle");
  const [operatorEmail, setOperatorEmail] = useState("");
  const [digestConsent, setDigestConsent] = useState(false);
  const [frames, setFrames] = useState<TickFrame[]>([]);
  const [completedRecording, setCompletedRecording] = useState<Recording | null>(null);
  const [cursor, setCursor] = useState(0);
  const [networkView, setNetworkView] = useState<"grid" | "spatial">("grid");
  const [spatialArm, setSpatialArm] = useState<"baseline" | "vidyut">("vidyut");
  const [selectedDt, setSelectedDt] = useState("F1-DT17");

  const progress = phase === "Complete" ? 100 : busy ? 58 : 0;
  const assets = useMemo(
    () => Object.entries(flexibility?.registered.capacity_by_kind_kw ?? {}).sort((a, b) => b[1] - a[1]),
    [flexibility],
  );

  async function waitForRun(id: string) {
    for (let attempt = 0; attempt < 240; attempt += 1) {
      const state = await api<{ status: string; error: string | null }>(`/api/runs/${id}`);
      setPhase(state.status === "running" ? "Simulating both control strategies" : titleCase(state.status));
      if (state.status === "ready") return;
      if (state.status === "failed") throw new Error(state.error ?? "Simulation failed");
      await new Promise((resolve) => window.setTimeout(resolve, 500));
    }
    throw new Error("The simulation did not finish within two minutes");
  }

  function collectFrames(id: string) {
    return new Promise<TickFrame[]>((resolve, reject) => {
      const socket = new WebSocket(
        `${API_URL.replace(/^http/, "ws")}/ws/runs/${id}?speed=200`,
      );
      const collected: TickFrame[] = [];
      let settled = false;
      const finish = () => {
        if (settled) return;
        settled = true;
        socket.close();
        setFrames(collected);
        setCursor(collected.length ? collected.length - 1 : 0);
        if (collected.length) setNetworkView("spatial");
        resolve(collected);
      };
      const fail = (message: string) => {
        if (settled) return;
        settled = true;
        socket.close();
        reject(new Error(message));
      };
      socket.onmessage = (message) => {
        const payload = JSON.parse(message.data);
        if (payload.type === "tick") collected.push(payload as TickFrame);
        else if (payload.type === "complete") finish();
        else if (payload.type === "error") fail(payload.detail ?? "The network replay could not be streamed");
      };
      socket.onerror = () => fail("The network replay connection failed");
      window.setTimeout(() => fail("The network replay did not arrive within 30 seconds"), 30000);
    });
  }

  async function runSimulation() {
    setBusy(true);
    setError(null);
    setSummary(null);
    setFlexibility(null);
    setEvents(null);
    setNotifications(null);
    setDispatchResult(null);
    setDispatchPhase("idle");
    setFrames([]);
    setCompletedRecording(null);
    setCursor(0);
    setPhase("Creating run");
    try {
      const created = await api<{ run_id: string; status: string }>("/api/runs", {
        method: "POST",
        body: JSON.stringify({
          scenario,
          seed,
          ticks,
          carry_debt: true,
          params: advanced ? params : {},
        }),
      });
      setRunId(created.run_id);
      await waitForRun(created.run_id);
      setPhase("Loading audited results");
      const [nextSummary, nextFlexibility, nextEvents, nextNotifications] = await Promise.all([
        api<RunSummary>(`/api/runs/${created.run_id}/summary`),
        api<RunFlexibility>(`/api/runs/${created.run_id}/flexibility`),
        api<EventResponse>(`/api/runs/${created.run_id}/events?arm=vidyut&limit=1000`),
        api<NotificationResponse>(`/api/runs/${created.run_id}/notifications`),
      ]);
      setSummary(nextSummary);
      setFlexibility(nextFlexibility);
      setEvents(nextEvents);
      setNotifications(nextNotifications);
      setPhase("Streaming the network");
      const nextFrames = await collectFrames(created.run_id);
      const nextRecording: Recording = {
        meta: {
          schema_version: 1,
          scenario,
          seed,
          ticks: nextFrames.length,
          arms: ["baseline", "vidyut"],
          simulated: true,
        },
        ticks: nextFrames,
        summary: { arms: nextSummary.arms, deltas: nextSummary.deltas },
        notifications: [],
      };
      setCompletedRecording(nextRecording);
      setPhase("Complete");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not run the simulation");
      setPhase("Run failed");
    } finally {
      setBusy(false);
    }
  }

  async function dispatchNotifications() {
    if (!runId || !notifications?.count) return;
    if (!operatorEmail.trim() || !digestConsent) {
      setError("Enter the operator email and confirm one-time use before sending.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await api<{ status: string; accepted: boolean; configured: boolean; notification_count: number; tracking: boolean; error: string | null }>(
        `/api/runs/${runId}/notifications/dispatch`,
        {
          method: "POST",
          body: JSON.stringify({ recipient_email: operatorEmail, consent: true }),
        },
      );
      if (!result.accepted) {
        setDispatchPhase("failed");
        setDispatchResult(result.error ?? "The n8n operator workflow is not configured.");
        return;
      }
      setDispatchPhase("accepted");
      setDispatchResult(`n8n accepted one simulated operator digest covering ${result.notification_count} queued broadcasts.`);
      setOperatorEmail("");
      setDigestConsent(false);
      if (result.tracking) void pollDelivery(runId);
    } catch (caught) {
      setDispatchPhase("failed");
      setError(caught instanceof Error ? caught.message : "Dispatch failed");
    } finally {
      setBusy(false);
    }
  }

  async function pollDelivery(id: string) {
    for (let attempt = 0; attempt < 30; attempt += 1) {
      await new Promise((resolve) => window.setTimeout(resolve, 1000));
      try {
        const delivery = await api<{ status: string; delivered_at: string | null; error: string | null }>(`/api/runs/${id}/notifications/delivery`);
        if (delivery.status === "delivered") {
          const when = delivery.delivered_at ? new Date(delivery.delivered_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "now";
          setDispatchPhase("delivered");
          setDispatchResult(`Operator digest delivered at ${when}. The address was not retained by Vidyut.`);
          return;
        }
        if (delivery.status === "failed") {
          setDispatchPhase("failed");
          setDispatchResult(delivery.error ?? "The email provider reported a delivery failure.");
          return;
        }
      } catch {
        return;
      }
    }
    setDispatchResult("n8n accepted the digest. Delivery confirmation is still pending.");
  }

  const comparison = summary
    ? [
        ["Homes-dark minutes", summary.arms.baseline.homes_dark_minutes, summary.arms.vidyut.homes_dark_minutes, "min", false],
        ["Unserved energy", summary.arms.baseline.unserved_kwh, summary.arms.vidyut.unserved_kwh, "kWh", false],
        ["Critical uptime", summary.arms.baseline.critical_uptime_pct, summary.arms.vidyut.critical_uptime_pct, "%", true],
        ["Maximum transformer load", summary.arms.baseline.max_trafo_loading_pct, summary.arms.vidyut.max_trafo_loading_pct, "%", false],
      ] as const
    : [];

  return (
    <main className="workspace simulation-workspace">
      <section className="workspace-hero">
        <div>
          <p className="eyebrow">Scenario laboratory</p>
          <h1>Stress the network.<br />Inspect the response.</h1>
          <p className="lede">Run the same demand twice: once with conventional protection and once with Vidyut. Every result below comes from the backend simulation.</p>
        </div>
        <aside className="run-builder panel">
          <div className="panel-heading">
            <div><span>New simulation</span><strong>{phase}</strong></div>
            <span className={`status-dot ${online ? "is-online" : "is-offline"}`}>{online ? "API ready" : "API offline"}</span>
          </div>
          <div className="form-grid three">
            <label>Scenario<select value={scenario} onChange={(event) => setScenario(event.target.value as ScenarioName)} disabled={busy}><option value="normal">Normal day</option><option value="heatwave">Heatwave</option><option value="ev_surge">EV surge</option></select></label>
            <label>Random seed<input type="number" value={seed} onChange={(event) => setSeed(Number(event.target.value))} disabled={busy} /></label>
            <label>15-minute intervals<input type="number" min="1" max="96" value={ticks} onChange={(event) => setTicks(Math.max(1, Math.min(96, Number(event.target.value))))} disabled={busy} /></label>
          </div>
          <button className="text-button" type="button" onClick={() => setAdvanced((value) => !value)} aria-expanded={advanced}>{advanced ? "Hide scenario assumptions" : "Adjust scenario assumptions"}</button>
          {advanced && <div className="advanced-grid">
            {Object.entries(params).map(([key, value]) => <label key={key}>{titleCase(key)}<input type="number" step="0.01" value={value} onChange={(event) => setParams((current) => ({ ...current, [key]: Number(event.target.value) }))} /></label>)}
          </div>}
          <button className="primary-action" onClick={runSimulation} disabled={!online || busy}>{busy ? "Running simulation…" : `Run ${ticks === 96 ? "full day" : `${ticks} intervals`}`}</button>
          <div className="run-progress"><i style={{ width: `${progress}%` }} /><span>{ticks * 15} simulated minutes · baseline + Vidyut</span></div>
          {error && <p className="inline-error" role="alert">{error}</p>}
        </aside>
      </section>

      {!summary ? <section className="preflight-grid">
        <article><span>01</span><strong>Identical demand</strong><p>Both arms receive the same network, households, weather and seed.</p></article>
        <article><span>02</span><strong>Different control</strong><p>The baseline protects equipment reactively. Vidyut can forecast and target flexibility.</p></article>
        <article><span>03</span><strong>Auditable output</strong><p>Events, notifications, fairness debt and a generated PDF are retained with the run.</p></article>
      </section> : <>
        <section className="results-section">
          <div className="section-heading"><div><p className="eyebrow">Run outcome</p><h2>One demand profile. Two futures.</h2></div><div className="run-identity"><span>Run ID</span><code>{runId}</code></div></div>
          <div className="comparison-table">
            <div className="comparison-head"><span>Outcome</span><span>Baseline</span><span>Vidyut</span><span>Difference</span></div>
            {comparison.map(([label, baseline, vidyut, unit, higherBetter]) => {
              const delta = vidyut - baseline;
              const improved = higherBetter ? delta >= 0 : delta <= 0;
              return <div className="comparison-row" key={label}><strong>{label}<small>{unit}</small></strong><span>{formatNumber(baseline)}</span><span>{formatNumber(vidyut)}</span><span className={improved ? "positive" : "negative"}>{delta > 0 ? "+" : ""}{formatNumber(delta)}</span></div>;
            })}
          </div>
          <div className="result-actions">
            <div>
              <button className="primary-action" type="button" disabled={!completedRecording || !runId} onClick={() => completedRecording && runId && onOpenCommandCenter(completedRecording, runId)}>Open in command center →</button>
              <button className="secondary-action button" type="button" disabled={!frames.length} onClick={() => { setNetworkView("spatial"); window.requestAnimationFrame(() => document.getElementById("simulation-network")?.scrollIntoView({ behavior: "smooth", block: "start" })); }}>View 3D network ↓</button>
              <a className="secondary-action" href={`${API_URL}/api/runs/${runId}/report`} target="_blank" rel="noreferrer">Open audit report ↗</a>
            </div>
            <span>{events?.total ?? 0} controller events · {notifications?.count ?? 0} notifications pending</span>
          </div>
        </section>

        {frames.length > 0 && (() => {
          const frame = frames[Math.min(cursor, frames.length - 1)];
          const targets = new Set(frame.arms.vidyut.events.map((event) => event.target));
          return (
            <section className="results-section" id="simulation-network">
              <div className="section-heading">
                <div><p className="eyebrow">Your run · the network hour by hour</p><h2>{frame.clock}</h2><p className="section-note">Drag the timeline to move through the day. Click any transformer to inspect it.</p></div>
                <div className="view-toggle" role="group" aria-label="Network view">
                  <button type="button" className={networkView === "grid" ? "active" : ""} onClick={() => setNetworkView("grid")} aria-pressed={networkView === "grid"}>Grid</button>
                  <button type="button" className={networkView === "spatial" ? "active" : ""} onClick={() => setNetworkView("spatial")} aria-pressed={networkView === "spatial"}>3D</button>
                </div>
                {networkView === "spatial" && <div className="arm-switch" role="group" aria-label="Spatial strategy"><button type="button" className={spatialArm === "baseline" ? "active danger" : ""} onClick={() => setSpatialArm("baseline")}>Baseline</button><button type="button" className={spatialArm === "vidyut" ? "active" : ""} onClick={() => setSpatialArm("vidyut")}>Vidyut</button></div>}
              </div>

              {networkView === "grid" ? <div className="network-compare">
                {([["baseline", frame.arms.baseline, "Baseline", undefined], ["vidyut", frame.arms.vidyut, "Vidyut", targets]] as const).map(([key, snapshot, title, active]) => (
                  <article className={`network-arm ${key}-arm`} key={key}>
                    <div className="arm-heading"><span><i />{title}</span><strong>{formatNumber(snapshot.metrics.max_trafo_loading_pct)}% <small>max loading</small></strong></div>
                    <TransformerGrid snapshot={snapshot} selectedDt={selectedDt} onSelect={setSelectedDt} activeTargets={active} />
                  </article>
                ))}
              </div> : <div className="network-compare spatial-single"><article className={`network-arm ${spatialArm}-arm`}><div className="arm-heading"><span><i />{spatialArm === "baseline" ? "Baseline" : "Vidyut"} spatial network</span><strong>{formatNumber(frame.arms[spatialArm].metrics.max_trafo_loading_pct)}% <small>max loading</small></strong></div><Network3D snapshot={frame.arms[spatialArm]} label={`${spatialArm} at ${frame.clock}`} selectedDt={selectedDt} onSelect={setSelectedDt} activeTargets={spatialArm === "vidyut" ? targets : new Set()} /></article></div>}

              <div className="frame-scrubber">
                <input type="range" min={0} max={frames.length - 1} value={cursor} onChange={(event) => setCursor(Number(event.target.value))} aria-label="Interval" />
                <div><span>midnight</span><span>midday</span><span>evening peak</span><span>midnight</span></div>
              </div>
            </section>
          );
        })()}

        <section className="results-grid">
          <article className="panel flexibility-panel">
            <div className="panel-heading"><div><span>Known flexibility</span><strong>{formatNumber(flexibility?.registered.capacity_kw, 0)} kW registered</strong></div><span className="source-chip registered">registered</span></div>
            <div className="capacity-stat"><strong>{flexibility?.registered.devices ?? 0}</strong><span>controllable devices across {flexibility?.registered.households ?? 0} homes</span></div>
            <div className="asset-bars">{assets.map(([kind, value]) => <div key={kind}><span>{titleCase(kind)}</span><i><b style={{ width: `${Math.max(3, value / Math.max(flexibility?.registered.capacity_kw ?? 1, 1) * 100)}%` }} /></i><em>{formatNumber(value, 0)} kW</em></div>)}</div>
            <div className="mini-stats"><div><span>Available peak</span><strong>{formatNumber(flexibility?.available.peak_kw)} kW</strong></div><div><span>Realised reduction</span><strong>{formatNumber(flexibility?.realised.reduction_kwh)} kWh</strong></div></div>
          </article>

          <article className="panel events-panel">
            <div className="panel-heading"><div><span>Controller trace</span><strong>{events?.total ?? 0} recorded actions</strong></div><span className="source-chip simulated">simulated</span></div>
            <div className="event-list">{events?.events.slice(0, 6).map((event, index) => <div key={`${event.t}-${event.target}-${index}`}><span className={`tier-tag tier-${event.tier}`}>T{event.tier}</span><p><strong>{titleCase(event.action)}</strong><small>Tick {event.t} · {event.target} · {formatNumber(event.kw)} kW</small></p><em>{event.households ? `${event.households} homes` : "network"}</em></div>)}</div>
            {(events?.total ?? 0) > 6 && <p className="panel-note">Showing the first six of {events?.total} events. The complete trace is retained by the API.</p>}
          </article>

          <article className="panel notification-panel">
            <div className="panel-heading"><div><span>Operator automation</span><strong>{notifications?.count ?? 0} broadcasts summarised</strong></div><span className="source-chip operational">n8n</span></div>
            {notifications?.notifications.length ? <>
              <div className="message-preview"><span>Resident preview only · not sent · {notifications.notifications[0].clock}</span><p>{notifications.notifications[0].message}</p></div>
              <div className="operator-digest-form">
                <label>Operator email<input type="email" autoComplete="email" placeholder="operator@example.com" value={operatorEmail} onChange={(event) => setOperatorEmail(event.target.value)} disabled={busy || dispatchPhase === "accepted" || dispatchPhase === "delivered"} /></label>
                <label className="consent-row"><input type="checkbox" checked={digestConsent} onChange={(event) => setDigestConsent(event.target.checked)} disabled={busy || dispatchPhase === "accepted" || dispatchPhase === "delivered"} /><span>Use this address once for this simulated digest. Vidyut will not store it.</span></label>
                <button className="secondary-action button" onClick={dispatchNotifications} disabled={busy || !operatorEmail.trim() || !digestConsent || dispatchPhase === "accepted" || dispatchPhase === "delivered"}>{busy ? "Sending to n8n…" : "Send simulated operator digest"}</button>
              </div>
              {dispatchResult && <p className={`delivery-state ${dispatchPhase}`} aria-live="polite"><i />{dispatchResult}</p>}
            </> : <div className="compact-empty">No notifications were required for this run.</div>}
          </article>
        </section>
      </>}
    </main>
  );
}
