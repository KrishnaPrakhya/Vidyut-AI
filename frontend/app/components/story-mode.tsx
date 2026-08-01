"use client";

import { useEffect, useMemo, useState } from "react";
import { buildStory, formatNumber, groupEvents, actionGlyph, actionLabel } from "../lib/replay";
import type { ArmName, Recording } from "../types";
import { TransformerGrid } from "./transformer-grid";

type Props = {
  recording: Recording;
  onExplore: () => void;
};

function Locality({ darkHomes }: { darkHomes: number }) {
  const darkDots = Math.min(14, Math.ceil(darkHomes / 5));
  return (
    <div className="locality" aria-label={`${darkHomes} homes without power`}>
      {Array.from({ length: 14 }, (_, index) => <i className={index < darkDots ? "dark" : "lit"} key={index} />)}
    </div>
  );
}

export function StoryMode({ recording, onExplore }: Props) {
  const beats = useMemo(() => buildStory(recording), [recording]);
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(true);
  const beat = beats[index];
  const frame = recording.ticks[beat.tick];
  const arm: ArmName = ["forecast", "control", "protected"].includes(beat.kind) ? "vidyut" : "baseline";
  const focusBaseline = frame.arms.baseline.dts.find((dt) => dt.id === beat.focusDt);
  const focusVidyut = frame.arms.vidyut.dts.find((dt) => dt.id === beat.focusDt);
  const targetEvents = frame.arms.vidyut.events.filter((event) => !beat.focusDt || event.target === beat.focusDt);
  const activeTargets = new Set(frame.arms.vidyut.events.map((event) => event.target));

  useEffect(() => {
    if (!playing) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) return;
    const delay = index === beats.length - 1 ? 4200 : 2300;
    const timer = window.setTimeout(() => {
      if (index === beats.length - 1) setPlaying(false);
      else setIndex((value) => value + 1);
    }, delay);
    return () => window.clearTimeout(timer);
  }, [beats.length, index, playing]);

  function replay() {
    setIndex(0);
    setPlaying(true);
  }

  return (
    <section className={`story story-${beat.kind}`}>
      <div className="story-topline">
        <div><span className="live-dot" />Recorded heatwave · seed {recording.meta.seed}</div>
        <button type="button" className="text-button" onClick={onExplore}>Skip to interactive replay →</button>
      </div>

      <div className="story-stage" key={beat.id}>
        <div className="story-copy">
          <span className="story-step">{String(index + 1).padStart(2, "0")} / {String(beats.length).padStart(2, "0")}</span>
          <p>{beat.label}</p>
          <h1>{beat.title}</h1>
          <p className="story-body">{beat.body}</p>
          <div className="story-value"><strong>{beat.primary}</strong><span>{beat.secondary}</span></div>
        </div>

        <div className="story-visual" aria-live="polite">
          {beat.kind === "heat" && (
            <div className="heat-visual">
              <div className="sun-disc"><span>HEATWAVE</span></div>
              <div className="demand-rise">
                {recording.ticks.slice(Math.max(0, beat.tick - 8), beat.tick + 1).map((tick) => <i key={tick.t} style={{ height: `${tick.arms.baseline.metrics.max_trafo_loading_pct}%` }} />)}
              </div>
              <p>Transformer demand rising into the evening peak</p>
            </div>
          )}

          {(beat.kind === "overload" || beat.kind === "forecast") && (
            <div className="transformer-focus">
              <div className="transformer-shell">
                <div className="coil"><i /><i /><i /></div>
                <span>{beat.focusDt}</span>
              </div>
              <div className="load-gauge">
                <i style={{ width: `${Math.min(100, beat.kind === "forecast" ? ((targetEvents[0]?.forecast_kw ?? 0) / (targetEvents[0]?.safe_limit_kw ?? 1)) * 90 : focusBaseline?.loading_pct ?? 0)}%` }} />
                <span className="safe-marker">safe</span>
              </div>
              <div className="gauge-labels"><span>0%</span><strong>{beat.primary}</strong><span>125%</span></div>
            </div>
          )}

          {beat.kind === "outage" && (
            <div className="outage-visual">
              <Locality darkHomes={focusBaseline?.households_dark ?? 0} />
              <div className="outage-line"><span />Transformer disconnected<span /></div>
            </div>
          )}

          {beat.kind === "control" && (
            <div className="control-stack">
              {groupEvents(targetEvents).map((event, eventIndex) => (
                <div className="control-action" key={event.action} style={{ animationDelay: `${eventIndex * 120}ms` }}>
                  <b>{actionGlyph(event.action)}</b>
                  <span><strong>{actionLabel(event.action)}</strong><small>{formatNumber(event.kw)} kW · {event.households} household actions</small></span>
                </div>
              ))}
              {targetEvents.length === 0 && <p>Previously issued controls remain active through this interval.</p>}
            </div>
          )}

          {beat.kind === "protected" && (
            <div className="protected-visual">
              <Locality darkHomes={focusVidyut?.households_dark ?? 0} />
              <div className="critical-service"><b>+</b><span>Critical services<strong>100% uptime</strong></span></div>
            </div>
          )}

          {beat.kind === "outcome" && (
            <div className="outcome-visual">
              <div className="outcome-column baseline"><span>Baseline</span><strong>{formatNumber(recording.summary.arms.baseline.homes_dark_minutes, 0)}</strong><small>homes-dark minutes</small></div>
              <div className="outcome-arrow">→</div>
              <div className="outcome-column vidyut"><span>Vidyut</span><strong>{formatNumber(recording.summary.arms.vidyut.homes_dark_minutes, 0)}</strong><small>homes-dark minutes</small></div>
              <div className="outcome-reduction">{formatNumber(100 * (1 - recording.summary.arms.vidyut.homes_dark_minutes / recording.summary.arms.baseline.homes_dark_minutes), 1)}% lower</div>
            </div>
          )}

          {beat.kind !== "outcome" && beat.kind !== "heat" && (
            <div className="story-network">
              <TransformerGrid snapshot={frame.arms[arm]} selectedDt={beat.focusDt ?? ""} onSelect={() => undefined} activeTargets={activeTargets} compact />
              <div className="story-legend"><span><i className="stable" />stable</span><span><i className="strained" />strained</span><span><i className="overloaded" />overloaded</span><span><i className="offline" />off</span></div>
            </div>
          )}
        </div>
      </div>

      <div className="story-controls">
        <button type="button" className="play-control" onClick={() => index === beats.length - 1 ? replay() : setPlaying((value) => !value)} aria-label={index === beats.length - 1 ? "Replay story" : playing ? "Pause story" : "Play story"}>
          {index === beats.length - 1 ? "↺" : playing ? "Ⅱ" : "▶"}
        </button>
        <div className="story-progress">
          {beats.map((item, itemIndex) => <button type="button" key={item.id} className={itemIndex <= index ? "passed" : ""} onClick={() => { setIndex(itemIndex); setPlaying(false); }} aria-label={`Show story step ${itemIndex + 1}`}><i /></button>)}
        </div>
        <span>{frame.clock}</span>
      </div>
    </section>
  );
}
