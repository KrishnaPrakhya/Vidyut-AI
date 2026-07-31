"use client";

import Link from "next/link";

export default function Hero() {
  return (
    <section className="hero">
      <div>
        <p className="kicker">AI-POWERED LOAD BALANCING FOR ELECTRICAL GRIDS</p>
        <h1>Vidyut AI Command Center</h1>
        <p className="intro">
          Every second, billions of requests are balanced across servers so no machine sits at 100% while another idles. Electricity doesn&apos;t work that way — until now. Vidyut balances electrical demand across distribution networks using forecasting, demand flexibility, and feeder reconfiguration.
        </p>

        <div style={{ display: "flex", gap: 16, marginTop: 28 }}>
          <Link href="/dashboard" className="primary" style={{ padding: "14px 28px", fontSize: 16, textDecoration: "none" }}>
            Launch AI Command Center →
          </Link>
          <Link href="/simulation" className="secondary" style={{ padding: "14px 24px", fontSize: 16, textDecoration: "none" }}>
            Simulation Console
          </Link>
        </div>
      </div>

      <div className="hero-visual-card">
        <div style={{ padding: 24, background: "var(--dark)", color: "white", borderRadius: 4, border: "1px solid var(--dark)" }}>
          <span className="kicker" style={{ color: "var(--green)" }}>LIVE GRID TWIN DEMO</span>
          <h3 style={{ margin: "8px 0 12px", fontSize: 22, color: "white" }}>60 DTs • 3 Feeders • 4,200 Homes</h3>
          <p style={{ fontSize: 13, color: "#aebdb4", lineHeight: 1.5 }}>
            Real-time AC power flow calculation comparing Baseline utility practice against Vidyut&apos;s 3-tier pre-emptive load balancing.
          </p>
          <div style={{ marginTop: 20, paddingTop: 16, borderTop: "1px solid #334155", display: "flex", justifyContent: "space-between", fontSize: 11, fontFamily: "monospace" }}>
            <span>FEEDER 1: 61%</span>
            <span>FEEDER 2: 75%</span>
            <span>FEEDER 3: 84%</span>
          </div>
        </div>
      </div>
    </section>
  );
}
