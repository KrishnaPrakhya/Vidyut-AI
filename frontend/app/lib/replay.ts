import type { Recording, StoryBeat, TickEvent, TickFrame } from "../types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = init?.body === undefined
    ? init?.headers
    : { "Content-Type": "application/json", ...init?.headers };
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function formatNumber(value: number | null | undefined, digits = 1) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat("en-IN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

export function actionLabel(action: string) {
  const labels: Record<string, string> = {
    price_signal: "Price signal",
    device_shift: "Flexible load shifted",
    device_curtail: "Connected devices reduced",
    meter_load_limit: "Temporary load limit",
    rotational_disconnect: "Rotating interruption",
    reconfigure: "Grid reconfigured",
    dt_de_energise: "Transformer switched off",
    dt_restore: "Transformer restored",
  };
  return labels[action] ?? action.replaceAll("_", " ");
}

export function actionGlyph(action: string) {
  const glyphs: Record<string, string> = {
    price_signal: "₹",
    device_shift: "↪",
    device_curtail: "⌁",
    meter_load_limit: "↓",
    rotational_disconnect: "!",
    reconfigure: "⇄",
    dt_de_energise: "×",
    dt_restore: "↟",
  };
  return glyphs[action] ?? "·";
}

export function titleCase(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function groupEvents(events: TickEvent[]) {
  const groups = new Map<string, { action: string; count: number; kw: number; households: number }>();
  for (const event of events) {
    const existing = groups.get(event.action) ?? {
      action: event.action,
      count: 0,
      kw: 0,
      households: 0,
    };
    existing.count += 1;
    existing.kw += event.kw;
    existing.households += event.households;
    groups.set(event.action, existing);
  }
  return [...groups.values()].sort((a, b) => b.kw - a.kw);
}

function topTransformer(frame: TickFrame, arm: "baseline" | "vidyut") {
  return [...frame.arms[arm].dts].sort((a, b) => b.loading_pct - a.loading_pct)[0];
}

export function buildStory(recording: Recording): StoryBeat[] {
  const overload = recording.ticks.find(
    (frame) => frame.arms.baseline.metrics.max_trafo_loading_pct >= 100,
  ) ?? recording.ticks[65];
  const focus = topTransformer(overload, "baseline").id;
  const outage = recording.ticks.find(
    (frame) => frame.t >= overload.t && frame.arms.baseline.dts.some((dt) => dt.id === focus && !dt.energized),
  ) ?? overload;
  const prediction = [...recording.ticks]
    .slice(0, overload.t + 1)
    .reverse()
    .find((frame) => frame.arms.vidyut.events.some((event) => event.target === focus && event.forecast_kw));
  const predictionEvent = prediction?.arms.vidyut.events.find(
    (event) => event.target === focus && event.forecast_kw,
  );
  const comparison = recording.ticks[Math.max(outage.t - 1, 0)];
  const baselineDt = comparison.arms.baseline.dts.find((dt) => dt.id === focus);
  const outageBaseline = outage.arms.baseline.dts.find((dt) => dt.id === focus);
  const outageVidyut = outage.arms.vidyut.dts.find((dt) => dt.id === focus);
  const baselineTotals = recording.summary.arms.baseline;
  const vidyutTotals = recording.summary.arms.vidyut;
  const actionCount = prediction?.arms.vidyut.events
    .filter((event) => event.target === focus)
    .reduce((total, event) => total + event.households, 0) ?? 0;

  return [
    {
      id: "heatwave",
      tick: Math.max(overload.t - 5, 0),
      label: "Heatwave · afternoon peak",
      title: "Demand rises across the network.",
      body: "Cooling demand climbs while every transformer serves the same homes in both simulations.",
      kind: "heat",
      focusDt: focus,
      primary: recording.ticks[Math.max(overload.t - 5, 0)].clock,
      secondary: "Same demand. Two control strategies.",
    },
    {
      id: "overload",
      tick: comparison.t,
      label: `Baseline · ${comparison.clock}`,
      title: `${focus} crosses its limit.`,
      body: "The conventional controller reacts only after the transformer is already overloaded.",
      kind: "overload",
      focusDt: focus,
      primary: `${formatNumber(baselineDt?.loading_pct)}%`,
      secondary: "Transformer loading",
    },
    {
      id: "outage",
      tick: outage.t,
      label: `Baseline · ${outage.clock}`,
      title: "The entire locality goes dark.",
      body: `${focus} is switched off to protect equipment. This is a transformer-level outage, not a targeted household action.`,
      kind: "outage",
      focusDt: focus,
      primary: `${outageBaseline?.households_dark ?? 0}`,
      secondary: "homes without power",
    },
    {
      id: "forecast",
      tick: prediction?.t ?? Math.max(overload.t - 1, 0),
      label: `Vidyut · ${prediction?.clock ?? overload.clock}`,
      title: "Vidyut sees the overload coming.",
      body: `${focus} is forecast above its safe limit before the baseline outage occurs.`,
      kind: "forecast",
      focusDt: focus,
      primary: `${formatNumber(predictionEvent?.forecast_kw, 0)} kW`,
      secondary: `Forecast · safe limit ${formatNumber(predictionEvent?.safe_limit_kw, 0)} kW`,
    },
    {
      id: "control",
      tick: prediction?.t ?? overload.t,
      label: "Targeted response",
      title: "Flexible demand moves first.",
      body: "Connected devices are briefly reduced and a temporary meter limit is used only where needed.",
      kind: "control",
      focusDt: focus,
      primary: `${actionCount}`,
      secondary: "targeted household actions at this transformer",
    },
    {
      id: "protected",
      tick: outage.t,
      label: `Vidyut · ${outage.clock}`,
      title: "The locality stays powered.",
      body: "The same transformer remains energised while critical services retain full uptime across the run.",
      kind: "protected",
      focusDt: focus,
      primary: `${formatNumber(outageVidyut?.loading_pct)}%`,
      secondary: `${outageVidyut?.households_dark ?? 0} homes dark · 100% critical uptime`,
    },
    {
      id: "outcome",
      tick: recording.ticks.length - 1,
      label: "End-of-day outcome",
      title: "A grid event becomes a controlled response.",
      body: "The result is not zero intervention. It is a far smaller, targeted burden with critical services protected.",
      kind: "outcome",
      focusDt: null,
      primary: `${formatNumber(baselineTotals.homes_dark_minutes, 0)} → ${formatNumber(vidyutTotals.homes_dark_minutes, 0)}`,
      secondary: `homes-dark minutes · ${formatNumber(baselineTotals.unserved_kwh)} → ${formatNumber(vidyutTotals.unserved_kwh)} kWh unserved`,
    },
  ];
}
