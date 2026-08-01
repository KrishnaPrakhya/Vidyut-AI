"use client";

import { useEffect, useState } from "react";
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

type AnalysisContext = {
  clock: string;
  transformerId: string;
  scenario: string;
};

export function AiExplainer({ frame, scenario, transformer }: AiExplainerProps) {
  const [question, setQuestion] = useState(prompts[0]);
  const [result, setResult] = useState<CopilotResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [analysisContext, setAnalysisContext] = useState<AnalysisContext | null>(null);

  useEffect(() => {
    if (!drawerOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setDrawerOpen(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [drawerOpen]);

  async function ask(nextQuestion = question) {
    setAnalysisContext({ clock: frame.clock, transformerId: transformer.id, scenario });
    setDrawerOpen(true);
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
    <div className="ai-head"><span><i>✦</i> Vidyut Copilot</span><b>ADVISORY</b></div>
    <h3>Ask about this moment</h3>
    <p>Get a plain-language answer grounded only in this recorded simulation.</p>
    <div className="ai-prompts ai-prompts-compact">{prompts.slice(0, 2).map((prompt) => <button type="button" key={prompt} className={question === prompt ? "active" : ""} onClick={() => void ask(prompt)} disabled={busy}>{prompt}</button>)}</div>
    <form className="ai-composer" onSubmit={(event) => { event.preventDefault(); void ask(); }}>
      <input value={question} onChange={(event) => setQuestion(event.target.value)} maxLength={300} aria-label="Question for Vidyut Copilot" />
      <button type="submit" aria-label="Ask Vidyut Copilot" disabled={busy || !question.trim()}>{busy ? "…" : "↑"}</button>
    </form>
    {(busy || result || error) && <button className="ai-open-analysis" type="button" onClick={() => setDrawerOpen(true)}>
      <span>{busy ? "ANALYSIS IN PROGRESS" : error ? "ANALYSIS NEEDS ATTENTION" : "LATEST EXPLANATION"}</span>
      <strong>{busy ? "Checking the recorded evidence…" : error ?? `${result?.evidence.length ?? 0} facts checked · ${result?.confidence ?? ""} confidence`}</strong>
      <b>{busy ? "Working" : "Open"} →</b>
    </button>}

    {drawerOpen && <aside className="ai-drawer" role="dialog" aria-modal="false" aria-labelledby="copilot-drawer-title">
      <header className="ai-drawer-head">
        <div><span><i>✦</i> VIDYUT COPILOT</span><h2 id="copilot-drawer-title">Explain this moment</h2></div>
        <div><b>LANGGRAPH · ADVISORY</b><button type="button" onClick={() => setDrawerOpen(false)} aria-label="Close Vidyut Copilot">×</button></div>
      </header>

      <div className="ai-drawer-context" aria-label="Selected simulation context">
        <span>LOCALITY<strong>{analysisContext?.transformerId ?? transformer.id}</strong></span>
        <span>REPLAY TIME<strong>{analysisContext?.clock ?? frame.clock}</strong></span>
        <span>SCENARIO<strong>{(analysisContext?.scenario ?? scenario).replaceAll("_", " ")}</strong></span>
      </div>

      <div className="ai-drawer-scroll" aria-live="polite">
        <div className="ai-drawer-prompts" aria-label="Suggested questions">{prompts.map((prompt) => <button type="button" key={prompt} className={question === prompt ? "active" : ""} onClick={() => void ask(prompt)} disabled={busy}>{prompt}</button>)}</div>

        {busy && <div className="agent-working drawer-working" role="status"><i /><div><strong>Checking recorded evidence</strong><span>Grounding context → selecting a specialist → verifying claims</span></div></div>}

        {result && <div className="ai-result">
          <section className="ai-drawer-answer">
            <div><span>WHAT VIDYUT SEES</span><b>{result.intent} · {result.confidence} confidence</b></div>
            <p>{result.explanation}</p>
          </section>

          <section className="ai-evidence-section">
            <div className="ai-section-title"><div><span>RECORDED EVIDENCE</span><h3>Numbers behind the answer</h3></div><b>{result.evidence.length} facts checked</b></div>
            <div className="agent-evidence" aria-label="Evidence used">{result.evidence.map((item) => <div key={item.id}><span>{item.label}</span><strong>{item.value}</strong><small>{item.source}</small></div>)}</div>
          </section>

          <details className="agent-trace">
            <summary><span>How the answer was checked</span><b>{result.trace.length} checks · {result.duration_ms} ms</b></summary>
            <ol>{result.trace.map((step, index) => <li key={`${step.node}-${index}`} className={step.status}><i>{index + 1}</i><div><strong>{step.label}</strong><span>{step.detail}</span></div></li>)}</ol>
          </details>
        </div>}

        {error && <div className="ai-drawer-error" role="alert"><span>THE COPILOT COULD NOT COMPLETE THIS REQUEST</span><p>{error}</p><button type="button" onClick={() => void ask()}>Try again</button></div>}
      </div>

      <form className="ai-drawer-composer" onSubmit={(event) => { event.preventDefault(); void ask(); }}>
        <label htmlFor="copilot-follow-up">Ask a follow-up about this recorded moment</label>
        <div><input id="copilot-follow-up" value={question} onChange={(event) => setQuestion(event.target.value)} maxLength={300} /><button type="submit" disabled={busy || !question.trim()}>{busy ? "Working…" : "Ask →"}</button></div>
      </form>
    </aside>}
  </section>;
}
