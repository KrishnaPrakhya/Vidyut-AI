"use client";

import { useEffect, useState } from "react";
import type { ModelsRegistry, OpportunityEstimate, VerificationResult } from "../types";
import { api, formatNumber, titleCase } from "../lib/replay";

type AssuranceLabProps = {
  online: boolean;
};

function ProfileChart({ values, label, tone = "estimated" }: { values: number[]; label: string; tone?: string }) {
  const max = Math.max(...values, 1);
  return <div className={`profile-chart ${tone}`} role="img" aria-label={label}>{values.map((value, index) => <i key={`${index}-${value}`} style={{ height: `${Math.max(4, value / max * 100)}%` }} title={`Interval ${index + 1}: ${formatNumber(value)} kW`} />)}</div>;
}

export function AssuranceLab({ online }: AssuranceLabProps) {
  const [registeredCapacity, setRegisteredCapacity] = useState(5);
  const [setpoint, setSetpoint] = useState(24);
  const [method, setMethod] = useState<"high_4_of_5" | "ten_in_ten">("high_4_of_5");
  const [committed, setCommitted] = useState(20);
  const [estimate, setEstimate] = useState<OpportunityEstimate | null>(null);
  const [verification, setVerification] = useState<VerificationResult | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [modelRegistry, setModelRegistry] = useState<ModelsRegistry | null>(null);

  useEffect(() => {
    if (!online) return;
    let active = true;
    api<ModelsRegistry>("/api/models")
      .then((result) => { if (active) setModelRegistry(result); })
      .catch(() => { if (active) setModelRegistry(null); });
    return () => { active = false; };
  }, [online]);

  const forecast = modelRegistry?.models.forecast;
  const improvement = (baseline: number | undefined, candidate: number | undefined) =>
    baseline && candidate !== undefined ? (baseline - candidate) / baseline * 100 : null;
  const hourGain = improvement(forecast?.by_horizon.seasonal_naive.next_hour.MASE, forecast?.by_horizon.chronos_finetuned.next_hour.MASE);
  const dayGain = improvement(forecast?.models.seasonal_naive.MASE, forecast?.models.chronos_finetuned.MASE);
  const coldGain = improvement(forecast?.cold_start.lgbm_from_scratch.MASE, forecast?.cold_start.chronos_finetuned.MASE);

  async function estimateOpportunity() {
    setBusy("estimate");
    setError(null);
    try {
      const ambient = Array.from({ length: 7 }, (_, day) =>
        [21, 22, 24, 27, 30, 32, 28, 24].map((value) => value + day * 0.35),
      );
      const aggregate = ambient.map((day, dayIndex) =>
        day.map((temperature, index) => 8 + dayIndex * 0.12 + 1.2 * Math.max(temperature - setpoint, 0) + index * 0.03),
      );
      const result = await api<OpportunityEstimate>("/api/observability/flexibility/estimate", {
        method: "POST",
        body: JSON.stringify({
          aggregate_kw: aggregate,
          ambient_c: ambient,
          registered_capacity_kw: registeredCapacity,
          setpoint_c: setpoint,
        }),
      });
      setEstimate(result);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Opportunity estimate failed");
    } finally {
      setBusy(null);
    }
  }

  async function verifyEvent() {
    setBusy("verify");
    setError(null);
    try {
      const history = Array.from({ length: method === "ten_in_ten" ? 10 : 5 }, (_, day) =>
        [98, 103, 110, 118, 126, 134, 128, 116].map((value, index) => value + day * 1.8 + index * 0.4),
      );
      const result = await api<VerificationResult>("/api/observability/events/verify", {
        method: "POST",
        body: JSON.stringify({
          history_kw: history,
          observed_kw: [105, 110, 116, 123, 109, 108, 126, 117],
          event_start_index: 4,
          event_end_index: 6,
          committed_reduction_kw: committed,
          method,
          adjustment_intervals: 4,
        }),
      });
      setVerification(result);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Event verification failed");
    } finally {
      setBusy(null);
    }
  }

  return (
    <main className="workspace assurance-workspace">
      <section className="assurance-hero">
        <div>
          <p className="eyebrow">Measurement assurance</p>
          <h1>Say what is known.<br />Prove what happened.</h1>
          <p className="lede">This workspace replaces appliance guessing with three explicit evidence levels. The source label travels with every number so an estimate can never masquerade as a measurement.</p>
        </div>
        <div className="evidence-ladder" aria-label="Evidence ladder">
          <article><span className="source-chip registered">registered</span><strong>Known capability</strong><p>Device nameplate and schedule data explicitly enrolled by a household.</p></article>
          <i aria-hidden="true">→</i>
          <article><span className="source-chip estimated">estimated</span><strong>Available opportunity</strong><p>A conservative AMI and weather estimate, capped by registered capacity.</p></article>
          <i aria-hidden="true">→</i>
          <article><span className="source-chip verified">verified</span><strong>Measured delivery</strong><p>Post-event measurement against an auditable comparison-day baseline.</p></article>
        </div>
      </section>

      {error && <p className="global-error" role="alert">{error}</p>}

      <section className="forecast-proof panel" aria-label="Forecast model evidence">
        <div className="forecast-proof-copy">
          <span className="source-chip verified">held-out evaluation</span>
          <h2>Chronos evidence, without a runtime claim.</h2>
          <p>{forecast?.trained ? `${forecast.n_series} real Indian meter and aggregate series were evaluated on the final held-out day.` : "The forecast evaluation artifact is not available on this API instance."}</p>
          <small>{forecast?.runtime_message ?? "The live simulation continues to report its actual forecaster in every tick."}</small>
        </div>
        <div className="forecast-proof-metrics">
          <div><span>Next hour</span><strong>{formatNumber(hourGain, 1)}%</strong><small>lower MASE than seasonal naive</small></div>
          <div><span>Full day</span><strong>{formatNumber(dayGain, 1)}%</strong><small>lower MASE than seasonal naive</small></div>
          <div><span>14-day cold start</span><strong>{formatNumber(coldGain, 1)}%</strong><small>lower MASE than from-scratch LGBM</small></div>
        </div>
        <div className="forecast-provenance"><i /><span><strong>{forecast?.data.real_measurements ? "Real measurements" : "Artifact unavailable"}</strong><small>{forecast?.data.sources?.[0] ?? "Start the API to load model provenance."}</small></span></div>
      </section>

      <section className="assurance-grid">
        <article className="method-card panel">
          <div className="method-index">01 · BEFORE AN EVENT</div>
          <div className="method-heading"><div><span className="source-chip estimated">estimated</span><h2>Estimate flexibility opportunity</h2></div><p>Fits the temperature-sensitive share of aggregate demand across comparable days. The result is an opportunity—not an appliance claim.</p></div>
          <div className="method-form">
            <label>Registered capacity cap<input type="number" min="0" step="0.5" value={registeredCapacity} onChange={(event) => setRegisteredCapacity(Math.max(0, Number(event.target.value)))} /><small>kW</small></label>
            <label>Cooling setpoint<input type="number" min="15" max="35" step="0.5" value={setpoint} onChange={(event) => setSetpoint(Number(event.target.value))} /><small>°C</small></label>
            <button className="primary-action" onClick={estimateOpportunity} disabled={!online || busy !== null}>{busy === "estimate" ? "Estimating…" : "Run transparent sample"}</button>
          </div>
          <p className="input-provenance">Sample input: seven days × eight intervals of paired aggregate load and ambient temperature.</p>
          {estimate ? <div className="method-result">
            <div className="result-verdict"><div><span>{titleCase(estimate.confidence)} confidence</span><strong>{formatNumber(estimate.actionable_peak_kw, 2)} kW</strong><small>actionable peak</small></div><div className="result-ring" style={{ "--ring": `${Math.min(100, estimate.coverage_pct)}%` } as React.CSSProperties}><strong>{formatNumber(estimate.coverage_pct, 0)}%</strong><small>coverage</small></div></div>
            <ProfileChart values={estimate.actionable_profile_kw ?? []} label="Estimated actionable flexibility across eight intervals" />
            <div className="method-stats"><div><span>Raw estimate</span><strong>{formatNumber(estimate.estimated_peak_kw, 2)} kW</strong></div><div><span>Registered cap</span><strong>{formatNumber(estimate.registered_capacity_kw, 2)} kW</strong></div><div><span>Temperature span</span><strong>{formatNumber(estimate.temperature_span_c, 1)} °C</strong></div><div><span>Fit score</span><strong>{formatNumber(estimate.fit_score, 2)}</strong></div></div>
            {estimate.reasons.length > 0 && <div className="reason-list">{estimate.reasons.map((reason) => <span key={reason}>{reason}</span>)}</div>}
          </div> : <div className="method-empty"><span>AMI</span><i>+</i><span>Weather</span><i>+</i><span>Registered cap</span><b>→</b><strong>Actionable envelope</strong></div>}
        </article>

        <article className="method-card panel verify-card">
          <div className="method-index">02 · AFTER AN EVENT</div>
          <div className="method-heading"><div><span className="source-chip verified">verified</span><h2>Verify delivered response</h2></div><p>Builds a comparison-day baseline, adjusts it using pre-event demand and measures the observed reduction during the event window.</p></div>
          <div className="method-form">
            <label>Baseline method<select value={method} onChange={(event) => setMethod(event.target.value as typeof method)}><option value="high_4_of_5">High 4 of 5</option><option value="ten_in_ten">10 in 10</option></select></label>
            <label>Committed reduction<input type="number" min="0" step="1" value={committed} onChange={(event) => setCommitted(Math.max(0, Number(event.target.value)))} /><small>kW</small></label>
            <button className="light-action" onClick={verifyEvent} disabled={!online || busy !== null}>{busy === "verify" ? "Verifying…" : "Verify sample event"}</button>
          </div>
          <p className="input-provenance">Sample input: interval history, event-day observations and a declared two-interval event window.</p>
          {verification ? <div className="method-result dark-result">
            <div className="verified-number"><span>Verified delivery</span><strong>{formatNumber(verification.realised_reduction_kw)} kW</strong><small>{formatNumber(verification.realised_reduction_kwh)} kWh across the event</small></div>
            <div className="baseline-compare"><div><span>Counterfactual baseline</span><i><b style={{ width: `${Math.min(100, verification.baseline_average_kw / Math.max(verification.baseline_average_kw, verification.observed_average_kw) * 100)}%` }} /></i><strong>{formatNumber(verification.baseline_average_kw)} kW</strong></div><div><span>Observed demand</span><i><b style={{ width: `${Math.min(100, verification.observed_average_kw / Math.max(verification.baseline_average_kw, verification.observed_average_kw) * 100)}%` }} /></i><strong>{formatNumber(verification.observed_average_kw)} kW</strong></div></div>
            <div className="method-stats"><div><span>Performance</span><strong>{formatNumber(verification.performance_pct, 0)}%</strong></div><div><span>Same-day adjustment</span><strong>{formatNumber(verification.same_day_adjustment_kw)} kW</strong></div><div><span>Coverage</span><strong>{formatNumber(verification.coverage_pct, 0)}%</strong></div><div><span>Method</span><strong>{titleCase(verification.method)}</strong></div></div>
          </div> : <div className="method-empty inverse"><span>History</span><i>+</i><span>Observed load</span><i>+</i><span>Event window</span><b>→</b><strong>Verified delivery</strong></div>}
        </article>
      </section>

      <section className="guardrail-strip">
        <div><span>Architectural guardrail</span><strong>Observability can measure and verify. It cannot issue an actuation command.</strong></div>
        <p>This boundary is enforced in the backend import graph. A confidence label, coverage score and source accompany every calculation.</p>
      </section>
    </main>
  );
}
