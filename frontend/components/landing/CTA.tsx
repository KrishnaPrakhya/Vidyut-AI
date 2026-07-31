"use client";

import Link from "next/link";

export default function CTA() {
  return (
    <section className="block" style={{ borderTop: "none" }}>
      <div
        className="run-card"
        style={{
          padding: "48px 32px",
          background: "var(--dark)",
          color: "white",
          borderColor: "var(--dark)",
          textAlign: "center",
        }}
      >
        <span className="kicker" style={{ color: "var(--green)" }}>READY TO EXPERIENCE THE FUTURE OF GRID AUTOMATION?</span>
        <h2 style={{ fontSize: 36, margin: "12px 0 16px", color: "white" }}>Launch the AI Command Center</h2>
        <p style={{ fontSize: 16, color: "#aebdb4", maxWidth: 600, margin: "0 auto 28px", lineHeight: 1.6 }}>
          Run real-time 24-hour simulations under live heatwaves, EV surges, and transformer fault contingencies.
        </p>

        <div style={{ display: "flex", gap: 16, justifyContent: "center" }}>
          <Link href="/dashboard" className="primary" style={{ padding: "14px 32px", fontSize: 16, textDecoration: "none" }}>
            Launch Command Center →
          </Link>
          <Link href="/simulation" className="secondary" style={{ padding: "14px 24px", fontSize: 16, textDecoration: "none" }}>
            Simulation Console
          </Link>
        </div>
      </div>
    </section>
  );
}
