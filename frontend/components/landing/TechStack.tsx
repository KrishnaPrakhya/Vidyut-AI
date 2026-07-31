"use client";

export default function TechStack() {
  const stack = [
    { layer: "Framework", tech: "Next.js 15 (App Router)" },
    { layer: "Language", tech: "TypeScript" },
    { layer: "State Management", tech: "Zustand" },
    { layer: "Styling & UI", tech: "Vanilla CSS Tokens & Glassmorphism" },
    { layer: "Simulation Engine", tech: "Python 3.11, pandapower" },
    { layer: "Forecasting", tech: "AutoGluon Chronos" },
    { layer: "Observability", tech: "PyTorch seq2point NILM" },
    { layer: "Backend API & WS", tech: "FastAPI, uvicorn, WebSockets" },
  ];

  return (
    <section className="block">
      <div className="heading">
        <div>
          <span className="kicker">TECHNOLOGY STACK</span>
          <h2>Production-Grade Engineering</h2>
        </div>
        <p>Built using modern Next.js 15 App Router, FastAPI REST/WebSocket, pandapower, and AutoGluon.</p>
      </div>

      <div className="run-card" style={{ padding: 24 }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 16 }}>
          {stack.map((item, idx) => (
            <div key={idx} style={{ padding: 14, background: "white", border: "1px solid var(--line)", borderRadius: 3 }}>
              <span className="kicker">{item.layer.toUpperCase()}</span>
              <strong style={{ display: "block", marginTop: 4, fontSize: 15, color: "var(--ink)" }}>{item.tech}</strong>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
