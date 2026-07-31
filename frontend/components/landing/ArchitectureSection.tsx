"use client";

export default function ArchitectureSection() {
  return (
    <section className="block">
      <div className="heading">
        <div>
          <span className="kicker">SYSTEM DESIGN</span>
          <h2>End-to-End System Architecture</h2>
        </div>
        <p>Decoupled multi-tier simulation architecture integrating AC power flow, time-series forecasting, and WebSocket streaming.</p>
      </div>

      <div className="run-card" style={{ padding: 32 }}>
        <div style={{ font: "700 13px ui-monospace, Consolas, monospace", color: "var(--muted)", marginBottom: 16 }}>
          VIDYUT ARCHITECTURE FLOW
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 16, textAlign: "center" }}>
          <div style={{ padding: 16, background: "white", border: "1px solid var(--line)" }}>
            <span style={{ fontSize: 24 }}>🏠</span>
            <strong style={{ display: "block", margin: "8px 0 4px", fontSize: 14 }}>4,200 Households</strong>
            <small style={{ color: "var(--muted)", fontSize: 11 }}>AMI + Smart Plugs</small>
          </div>

          <div style={{ padding: 16, background: "white", border: "1px solid var(--line)" }}>
            <span style={{ fontSize: 24 }}>⚡</span>
            <strong style={{ display: "block", margin: "8px 0 4px", fontSize: 14 }}>60 DT Buses</strong>
            <small style={{ color: "var(--muted)", fontSize: 11 }}>pandapower Grid</small>
          </div>

          <div style={{ padding: 16, background: "white", border: "1px solid var(--line)" }}>
            <span style={{ fontSize: 24 }}>🧠</span>
            <strong style={{ display: "block", margin: "8px 0 4px", fontSize: 14 }}>Vidyut Controller</strong>
            <small style={{ color: "var(--muted)", fontSize: 11 }}>3-Tier Optimizer</small>
          </div>

          <div style={{ padding: 16, background: "white", border: "1px solid var(--line)" }}>
            <span style={{ fontSize: 24 }}>📡</span>
            <strong style={{ display: "block", margin: "8px 0 4px", fontSize: 14 }}>FastAPI + WS</strong>
            <small style={{ color: "var(--muted)", fontSize: 11 }}>Tick Streaming</small>
          </div>

          <div style={{ padding: 16, background: "white", border: "1px solid var(--line)" }}>
            <span style={{ fontSize: 24 }}>📊</span>
            <strong style={{ display: "block", margin: "8px 0 4px", fontSize: 14 }}>AI Command Center</strong>
            <small style={{ color: "var(--muted)", fontSize: 11 }}>Next.js 15 Console</small>
          </div>
        </div>
      </div>
    </section>
  );
}
