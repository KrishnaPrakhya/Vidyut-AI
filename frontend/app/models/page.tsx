"use client";

import { useEffect, useState } from "react";
import Navbar from "../../components/layout/Navbar";
import Sidebar from "../../components/layout/Sidebar";
import { getModelsArtifacts, getObservabilityStatus } from "../../services/api";

type ModelArtifacts = {
  any_trained: boolean;
  models?: {
    forecast?: {
      trained: boolean;
      evaluation_only: boolean;
      runtime_ready: boolean;
      models?: Record<string, { MASE: number; MAPE: number }>;
      cold_start?: {
        history_days: number;
        lgbm_from_scratch?: { MASE: number };
        chronos_finetuned?: { MASE: number };
      };
      data?: { country: string; real_measurements: boolean; synthetic_training_data: boolean };
    };
  };
};

type ObservabilityStatus = {
  ready: boolean;
  boundaries: string[];
  capabilities: Record<string, boolean>;
};

export default function ModelsPage() {
  const [artifacts, setArtifacts] = useState<ModelArtifacts | null>(null);
  const [observability, setObservability] = useState<ObservabilityStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([
      getModelsArtifacts().catch(() => null),
      getObservabilityStatus().catch(() => null),
    ])
      .then(([modelsData, obsData]) => {
        if (!active) return;
        setArtifacts(modelsData);
        setObservability(obsData);
        setLoading(false);
      })
      .catch((err) => {
        if (!active) return;
        setError(err.message || "Failed to load model artifacts");
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const forecast = artifacts?.models?.forecast;
  const trained = forecast?.trained ?? false;
  const evalModels = forecast?.models || {};

  return (
    <div style={{ minHeight: "100vh" }}>
      <Navbar />

      <div style={{ display: "grid", gridTemplateColumns: "240px 1fr", gap: 24, padding: "24px 0" }}>
        <Sidebar />

        <div style={{ minWidth: 0 }}>
          <div className="heading">
            <div>
              <span className="kicker">EVALUATION &amp; VERIFICATION</span>
              <h2>AI Models &amp; Observability Proof</h2>
            </div>
            <p>Empirical evaluation on held-out distribution transformer series. Benchmark against seasonal naive baseline.</p>
          </div>

          {loading ? (
            <div className="empty">Loading evaluation artifacts...</div>
          ) : error ? (
            <div className="alert">{error}</div>
          ) : !trained ? (
            <div className="run-card" style={{ padding: 40, textAlign: "center" }}>
              <span className="kicker">NOT YET TRAINED</span>
              <h3 style={{ margin: "12px 0", fontSize: 24 }}>No Model Evaluation Artifact Found</h3>
              <p style={{ color: "var(--muted)", maxWidth: 500, margin: "0 auto 20px" }}>
                The forecasting evaluation artifact (<code>ml/artifacts/forecast_eval.json</code>) has not been generated yet.
              </p>
              <div style={{ font: "700 12px monospace", color: "var(--green-deep)" }}>
                Run <code>make train</code> or export model artifacts to populate this page.
              </div>
            </div>
          ) : (
            <div style={{ display: "grid", gap: 24 }}>
              {/* Status Banner */}
              <div className="run-card" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <span className="kicker">MODEL STATUS</span>
                  <h4 style={{ margin: "4px 0 0", fontSize: 18 }}>AutoGluon Chronos (bolt_small)</h4>
                </div>
                <div style={{ display: "flex", gap: 12 }}>
                  <span className={`source ${forecast?.evaluation_only ? "source-estimated" : "source-registered"}`}>
                    {forecast?.evaluation_only ? "EVALUATION ONLY" : "LIVE INFERENCE"}
                  </span>
                  <span className="source source-verified">
                    DATA: {forecast?.data?.country || "INDIA"}
                  </span>
                </div>
              </div>

              {/* Model Comparison Bars */}
              <div className="run-card">
                <span className="kicker">ACCURACY METRICS (LOWER IS BETTER)</span>
                <h3 style={{ margin: "8px 0 20px", fontSize: 22 }}>Forecast Evaluation across 96-tick Horizons</h3>

                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 20 }}>
                  {Object.entries(evalModels).map(([name, metrics]) => {
                    const isBest = name === "chronos_finetuned";
                    return (
                      <div
                        key={name}
                        style={{
                          padding: 20,
                          background: isBest ? "#edf8d3" : "white",
                          border: `1px solid ${isBest ? "#b8e34c" : "var(--line)"}`,
                          borderRadius: 4,
                        }}
                      >
                        <span className="kicker" style={{ color: isBest ? "#426f24" : "var(--muted)" }}>
                          {name.toUpperCase().replace("_", " ")}
                        </span>
                        <div style={{ fontSize: 32, fontWeight: 700, margin: "8px 0 4px", color: isBest ? "#284a11" : "var(--ink)" }}>
                          MASE {metrics.MASE.toFixed(4)}
                        </div>
                        <div style={{ fontSize: 13, color: "var(--muted)" }}>
                          MAPE: {metrics.MAPE.toFixed(2)}%
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* Cold Start Panel */}
                {forecast?.cold_start && (
                  <div style={{ marginTop: 28, paddingTop: 20, borderTop: "1px solid var(--line)" }}>
                    <span className="kicker">COLD START EVALUATION (14-DAY HISTORY)</span>
                    <div style={{ display: "flex", gap: 24, marginTop: 12 }}>
                      <div>
                        <span style={{ fontSize: 11, color: "var(--muted)" }}>LGBM from Scratch:</span>{" "}
                        <strong>MASE {forecast.cold_start.lgbm_from_scratch?.MASE.toFixed(4) || "—"}</strong>
                      </div>
                      <div>
                        <span style={{ fontSize: 11, color: "var(--muted)" }}>Chronos Fine-tuned:</span>{" "}
                        <strong style={{ color: "#284a11" }}>
                          MASE {forecast.cold_start.chronos_finetuned?.MASE.toFixed(4) || "—"}
                        </strong>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Observability Panel */}
              {observability && (
                <div className="run-card">
                  <span className="kicker">OBSERVABILITY ASSURANCE &amp; BOUNDARIES</span>
                  <h3 style={{ margin: "8px 0 16px", fontSize: 22 }}>NILM / Flexibility Disaggregation Rules</h3>
                  <p style={{ fontSize: 13, color: "var(--muted)", maxWidth: 700, margin: "0 0 16px" }}>
                    NILM provides non-intrusive load observability and post-event measurement &amp; verification (M&amp;V). It never issues direct actuation commands.
                  </p>

                  <div style={{ display: "grid", gap: 10 }}>
                    {observability.boundaries.map((boundary, i) => (
                      <div
                        key={i}
                        style={{
                          padding: "10px 14px",
                          background: "#fff1e9",
                          border: "1px solid #d28563",
                          color: "#7b3116",
                          fontSize: 13,
                        }}
                      >
                        ⚠️ {boundary}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
