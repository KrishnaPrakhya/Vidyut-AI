"use client";

import Navbar from "../components/layout/Navbar";
import Hero from "../components/landing/Hero";
import Features from "../components/landing/Features";
import ArchitectureSection from "../components/landing/ArchitectureSection";
import TechStack from "../components/landing/TechStack";
import CTA from "../components/landing/CTA";

export default function LandingPage() {
  return (
    <div>
      <Navbar />
      <Hero />

      {/* Problem Statement Section */}
      <section className="block">
        <div className="heading">
          <div>
            <span className="kicker">THE PROBLEM STATEMENT</span>
            <h2>Why Traditional Distribution Grids Fail</h2>
          </div>
          <p>Overloaded distribution transformers trigger widespread blackouts instead of balancing demand.</p>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
          <div className="run-card" style={{ padding: 24 }}>
            <span className="kicker" style={{ color: "#dc2626" }}>TRADITIONAL UTILITY PRACTICE</span>
            <h3 style={{ margin: "8px 0 10px", fontSize: 20 }}>Blunt Transformer Tripping</h3>
            <p style={{ fontSize: 14, color: "var(--muted)", lineHeight: 1.5 }}>
              When a distribution transformer hits 100%+ loading for consecutive intervals, traditional protection systems trip the entire transformer, disconnecting all 70 households downstream without selectivity or auditability.
            </p>
          </div>

          <div className="run-card" style={{ padding: 24, borderColor: "#b8e34c", background: "#fbfaf5" }}>
            <span className="kicker" style={{ color: "#486d2a" }}>VIDYUT AI COMMAND CENTER</span>
            <h3 style={{ margin: "8px 0 10px", fontSize: 20 }}>Continuous Pre-emptive Load Balancing</h3>
            <p style={{ fontSize: 14, color: "var(--ink)", lineHeight: 1.5 }}>
              Vidyut combines 4-tick ahead horizon forecasting with appliance flexibility shifting, pre-emptive greedy curtailment scored by comfort &amp; equity debt, and feeder tie-switch reconfiguration.
            </p>
          </div>
        </div>
      </section>

      <Features />
      <ArchitectureSection />
      <TechStack />
      <CTA />
    </div>
  );
}
