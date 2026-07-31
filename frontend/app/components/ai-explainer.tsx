"use client";

import { useState } from "react";
import type { DtSnapshot, TickFrame } from "../types";

type AiExplainerProps = {
  frame: TickFrame;
  scenario: string;
  transformer: DtSnapshot;
};

const prompts = [
  "Why is this transformer at risk?",
  "Explain the action to a resident.",
  "What changed versus baseline?",
];

export function AiExplainer({ frame, scenario, transformer }: AiExplainerProps) {
  const [question, setQuestion] = useState(prompts[0]);
  const [answer, setAnswer] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function ask(nextQuestion = question) {
    setBusy(true);
    setError(null);
    setQuestion(nextQuestion);
    try {
      const baselineTransformer = frame.arms.baseline.dts.find((item) => item.id === transformer.id);
      const vidyutTransformer = frame.arms.vidyut.dts.find((item) => item.id === transformer.id);
      const response = await fetch("/api/ai/explain", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: nextQuestion,
          scenario,
          clock: frame.clock,
          transformer: {
            id: transformer.id,
            baseline_loading_pct: baselineTransformer?.loading_pct,
            vidyut_loading_pct: vidyutTransformer?.loading_pct,
            baseline_homes_dark: baselineTransformer?.households_dark,
            vidyut_homes_dark: vidyutTransformer?.households_dark,
          },
          metrics: {
            baseline_network_max_loading_pct: frame.arms.baseline.metrics.max_trafo_loading_pct,
            vidyut_network_max_loading_pct: frame.arms.vidyut.metrics.max_trafo_loading_pct,
            vidyut_homes_dark: frame.arms.vidyut.metrics.homes_dark,
            vidyut_critical_uptime_pct: frame.arms.vidyut.metrics.critical_uptime_pct,
            vidyut_power_flow_converged: frame.arms.vidyut.metrics.converged,
          },
          forecast: frame.forecast && frame.forecast.dt_id === transformer.id ? {
            horizon_kw: frame.forecast.horizon_kw,
            safe_limit_kw: frame.forecast.safe_limit_kw,
            rating_kw: frame.forecast.rating_kw,
          } : null,
          events: frame.arms.vidyut.events,
        }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail ?? "Explanation failed");
      setAnswer(payload.explanation);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Explanation failed");
    } finally {
      setBusy(false);
    }
  }

  return <section className="ai-explainer">
    <div className="ai-head"><span><i>✦</i> Vidyut AI</span><b>ADVISORY ONLY</b></div>
    <h3>Explain this moment</h3>
    <p>Ask for a plain-language reading of the current simulated interval.</p>
    <div className="ai-prompts">{prompts.map((prompt) => <button type="button" key={prompt} className={question === prompt ? "active" : ""} onClick={() => ask(prompt)} disabled={busy}>{prompt}</button>)}</div>
    <form onSubmit={(event) => { event.preventDefault(); void ask(); }}><input value={question} onChange={(event) => setQuestion(event.target.value)} maxLength={300} aria-label="Question for Vidyut AI" /><button type="submit" disabled={busy || !question.trim()}>{busy ? "…" : "↑"}</button></form>
    {answer && <div className="ai-answer"><span>At {frame.clock} · {transformer.id}</span><p>{answer}</p></div>}
    {error && <p className="ai-error">{error}</p>}
  </section>;
}
