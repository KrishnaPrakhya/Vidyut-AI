"use client";

import Navbar from "../../components/layout/Navbar";
import Sidebar from "../../components/layout/Sidebar";

export default function AboutPage() {
  return (
    <div style={{ minHeight: "100vh" }}>
      <Navbar />

      <div style={{ display: "grid", gridTemplateColumns: "240px 1fr", gap: 24, padding: "24px 0" }}>
        <Sidebar />

        <div style={{ minWidth: 0, maxWidth: 900 }}>
          <div className="heading" style={{ display: "block" }}>
            <span className="kicker">POSITIONING &amp; ARCHITECTURE</span>
            <h2 style={{ fontSize: 36, margin: "8px 0 16px" }}>About Vidyut</h2>
            <p style={{ textTransform: "none", fontSize: 15, color: "#49544d", textAlign: "left", maxWidth: "100%" }}>
              Vidyut balances electrical demand across a distribution network using forecasting, demand flexibility, and feeder reconfiguration — continuously, and with an auditable record of who was affected and why.
            </p>
          </div>

          <div style={{ display: "grid", gap: 24, marginTop: 24 }}>
            {/* Mandatory Disclaimer */}
            <div style={{ padding: 18, background: "#fff0ca", border: "1px solid #926017", color: "#613c05", borderRadius: 4 }}>
              <strong>⚠️ DEMO SIMULATION DISCLAIMER:</strong>
              <div style={{ marginTop: 6, fontSize: 13 }}>
                This application runs a simulated 60-transformer 3-feeder distribution grid. It is <strong>not connected to any live utility system</strong>. A real deployment would require head-end/SCADA integration, IS 15959 / IEC 62351 security work, and regulatory approval.
              </div>
            </div>

            {/* Prior Art */}
            <div className="run-card">
              <span className="kicker">PRIOR ART &amp; EVIDENCE</span>
              <h3 style={{ margin: "8px 0 16px", fontSize: 20 }}>Existing Industry Deployments</h3>
              <ul style={{ display: "grid", gap: 12, paddingLeft: 20, fontSize: 14, lineHeight: 1.5, color: "#334155" }}>
                <li>
                  <strong>Household Demand Response in India:</strong> Tata Power with AutoGrid launched a DR programme in Mumbai targeting 55,000 residential and 6,000 C&amp;I consumers.
                </li>
                <li>
                  <strong>Automated DR Pilots:</strong> BSES Yamuna Power (BYPL) automated DR in Delhi reduced participating household demand by 17–20% during peak events.
                </li>
                <li>
                  <strong>Feeder Reconfiguration:</strong> Standard ADMS module in GE Vernova GridOS, Schneider EcoStruxure ADMS, and Oracle Utilities NMS (Baran &amp; Wu, 1989).
                </li>
                <li>
                  <strong>Smart Meter Rollout (RDSS):</strong> ~5.28 crore smart meters installed nationwide against RDSS sanctions covering 19.79 crore consumers.
                </li>
              </ul>
            </div>

            {/* Three Technical Principles */}
            <div className="run-card">
              <span className="kicker">TECHNICAL PRECISION</span>
              <h3 style={{ margin: "8px 0 16px", fontSize: 20 }}>Three Enforced Principles</h3>
              <div style={{ display: "grid", gap: 14 }}>
                <div style={{ padding: 14, background: "white", border: "1px solid var(--line)" }}>
                  <strong style={{ display: "block", color: "var(--ink)", marginBottom: 4 }}>1. Smart meters provide visibility. Actuation requires connected devices.</strong>
                  <span style={{ fontSize: 13, color: "var(--muted)" }}>
                    A smart meter measures load or enforces whole-service limits. Appliance-level control requires smart plugs, thermostats, OCPP EV chargers, or relays.
                  </span>
                </div>
                <div style={{ padding: 14, background: "white", border: "1px solid var(--line)" }}>
                  <strong style={{ display: "block", color: "var(--ink)", marginBottom: 4 }}>2. NILM is observability, not control.</strong>
                  <span style={{ fontSize: 13, color: "var(--muted)" }}>
                    Non-intrusive load monitoring estimates deferrable load shares and performs post-event measurement &amp; verification (M&amp;V). It never issues direct control commands.
                  </span>
                </div>
                <div style={{ padding: 14, background: "white", border: "1px solid var(--line)" }}>
                  <strong style={{ display: "block", color: "var(--ink)", marginBottom: 4 }}>3. Reconfiguration is topology, not power transfer.</strong>
                  <span style={{ fontSize: 13, color: "var(--muted)" }}>
                    Feeder agents propose tie-switch candidate configurations; pandapower validates radiality, voltage bounds (0.95–1.05 pu), and thermal constraints.
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
