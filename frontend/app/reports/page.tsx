"use client";

import Navbar from "../../components/layout/Navbar";
import Sidebar from "../../components/layout/Sidebar";
import { useSimulationStore } from "../../store/simulationStore";
import { API_URL } from "../../lib/constants";
import { formatNumber } from "../../lib/helpers";

export default function ReportsPage() {
  const { runId, summary } = useSimulationStore();
  const vidyut = summary?.arms?.vidyut || {};
  const baseline = summary?.arms?.baseline || {};

  const servedKwh = vidyut.served_kwh || 0;
  const unservedKwh = vidyut.unserved_kwh || 0;
  const unservedCost = vidyut.unserved_cost_rs || 0;

  return (
    <div style={{ minHeight: "100vh" }}>
      <Navbar />

      <div style={{ display: "grid", gridTemplateColumns: "240px 1fr", gap: 24, padding: "24px 0" }}>
        <Sidebar />

        <div style={{ minWidth: 0 }}>
          <div className="heading">
            <div>
              <span className="kicker">AUDIT &amp; COMPLIANCE</span>
              <h2>Incident &amp; Simulation Reports</h2>
            </div>
            <p>Auditable incident logs, affected transformer metrics, and downloadable PDF reports.</p>
          </div>

          <div style={{ display: "grid", gap: 24 }}>
            {/* Report Header Card */}
            <div className="run-card" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <span className="kicker">SIMULATION SUMMARY REPORT</span>
                <h3 style={{ margin: "4px 0 0", fontSize: 22 }}>
                  {runId ? `Run Report ID: ${runId}` : "Active Run Summary"}
                </h3>
              </div>

              {runId && (
                <a
                  href={`${API_URL}/api/runs/${runId}/report`}
                  target="_blank"
                  rel="noreferrer"
                  className="primary"
                  style={{ padding: "10px 20px", textDecoration: "none", fontSize: 14 }}
                >
                  📄 Download Official Incident Report (PDF)
                </a>
              )}
            </div>

            {/* Key Report Metrics */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 20 }}>
              <div className="run-card">
                <span className="kicker">TOTAL ENERGY DELIVERED</span>
                <div style={{ fontSize: 32, fontWeight: 700, margin: "8px 0 4px" }}>
                  {formatNumber(servedKwh, 0)} <small>kWh</small>
                </div>
                <div style={{ fontSize: 12, color: "var(--muted)" }}>
                  Baseline: {formatNumber(baseline.served_kwh, 0)} kWh
                </div>
              </div>

              <div className="run-card">
                <span className="kicker">UNSERVED ENERGY SAVED</span>
                <div style={{ fontSize: 32, fontWeight: 700, margin: "8px 0 4px", color: "#426f24" }}>
                  {formatNumber((baseline.unserved_kwh || 0) - unservedKwh, 1)} <small>kWh</small>
                </div>
                <div style={{ fontSize: 12, color: "var(--muted)" }}>
                  Avoided Outage Cost: ₹{formatNumber((baseline.unserved_cost_rs || 0) - unservedCost, 0)}
                </div>
              </div>

              <div className="run-card">
                <span className="kicker">CRITICAL INFRASTRUCTURE UPTIME</span>
                <div style={{ fontSize: 32, fontWeight: 700, margin: "8px 0 4px", color: "#486d2a" }}>
                  {formatNumber(vidyut.critical_uptime_pct || 100, 3)}%
                </div>
                <div style={{ fontSize: 12, color: "var(--muted)" }}>
                  Critical households fully protected
                </div>
              </div>
            </div>

            {/* Incident Audit Log */}
            <div className="run-card">
              <span className="kicker">AUDITABLE EVENT SUMMARY</span>
              <h3 style={{ margin: "8px 0 16px", fontSize: 20 }}>Transformer Intervention Summary</h3>
              <p style={{ fontSize: 14, color: "var(--muted)", lineHeight: 1.5 }}>
                Every intervention executed by Vidyut (device shifting, greedy curtailment, meter load limits, and rotational disconnects) is recorded with machine-generated, human-readable justification logs.
              </p>

              <div style={{ marginTop: 16, paddingTop: 16, borderTop: "1px solid var(--line)", fontSize: 13 }}>
                <strong>Report Download Status:</strong>{" "}
                {runId ? (
                  <span style={{ color: "var(--green-deep)" }}>
                    Ready for export via ReportLab PDF engine.
                  </span>
                ) : (
                  <span style={{ color: "var(--orange)" }}>
                    Run a simulation to generate an auditable PDF report.
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
