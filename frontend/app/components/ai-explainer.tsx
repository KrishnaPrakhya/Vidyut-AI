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
  "Draft an incident summary.",
];

type CopilotResponse = {
  explanation: string;
  intent: "risk" | "compare" | "resident" | "incident" | "general";
  audience: "operator" | "resident" | "reviewer";
  confidence: "high" | "medium";
  evidence: Array<{ id: string; label: string; value: string; source: string }>;
  trace: Array<{ node: string; label: string; detail: string; status: "complete" | "corrected" }>;
  orchestrator: "langgraph";
  duration_ms: number;
};

export function AiExplainer({ frame, scenario, transformer }: AiExplainerProps) {
  const [question, setQuestion] = useState(prompts[0]);
  const [result, setResult] = useState<CopilotResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function ask(nextQuestion = question) {
    setBusy(true);
    setError(null);
    setResult(null);
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
      setResult(payload as CopilotResponse);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Explanation failed");
    } finally {
      setBusy(false);
    }
  }

  return <section className="ai-explainer">
    <div className="ai-head"><span><i>✦</i> Vidyut Copilot</span><b>LANGGRAPH · ADVISORY</b></div>
    <h3>Investigate this moment</h3>
    <p>The copilot plans an evidence-bounded analysis, then verifies every numeric claim.</p>
    <div className="ai-prompts">{prompts.map((prompt) => <button type="button" key={prompt} className={question === prompt ? "active" : ""} onClick={() => ask(prompt)} disabled={busy}>{prompt}</button>)}</div>
    <form onSubmit={(event) => { event.preventDefault(); void ask(); }}><input value={question} onChange={(event) => setQuestion(event.target.value)} maxLength={300} aria-label="Question for Vidyut Copilot" /><button type="submit" disabled={busy || !question.trim()}>{busy ? "…" : "↑"}</button></form>
    {busy && <div className="agent-working" role="status"><i /><span>Grounding → planning → verifying</span></div>}
    {result && <div className="ai-result" aria-live="polite">
      <div className="ai-answer"><span>{frame.clock} · {transformer.id} · {result.intent} · {result.confidence} confidence</span><p>{result.explanation}</p></div>
      <div className="agent-evidence" aria-label="Evidence used">{result.evidence.map((item) => <div key={item.id}><span>{item.label}</span><strong>{item.value}</strong><small>{item.source}</small></div>)}</div>
      <details className="agent-trace">
        <summary><span>Agent audit path</span><b>{result.trace.length} nodes · {result.duration_ms} ms</b></summary>
        <ol>{result.trace.map((step, index) => <li key={`${step.node}-${index}`} className={step.status}><i>{index + 1}</i><div><strong>{step.label}</strong><span>{step.detail}</span></div></li>)}</ol>
      </details>
    </div>}
    {error && <p className="ai-error">{error}</p>}
  </section>;
}
