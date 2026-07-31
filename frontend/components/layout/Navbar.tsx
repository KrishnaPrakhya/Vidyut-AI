"use client";

import Link from "next/link";
import { useSimulationStore } from "../../store/simulationStore";
import { API_URL } from "../../lib/constants";

export default function Navbar() {
  const { offlineMode, runId } = useSimulationStore();

  return (
    <header className="navbar-container">
      <div className="brand">
        <span className="brand-logo">⚡</span>
        <span>
          <small>AI COMMAND CENTER</small>
          <strong>VIDYUT</strong>
        </span>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <div className={`health ${!offlineMode ? "online" : "offline"}`}>
          <i />
          <span>
            <b>SYSTEM STATUS</b>
            <small>{!offlineMode ? "LIVE BACKEND" : "OFFLINE REPLAY"}</small>
          </span>
        </div>

        {runId && (
          <a
            href={`${API_URL}/api/runs/${runId}/report`}
            target="_blank"
            rel="noreferrer"
            className="secondary"
            style={{ padding: "6px 12px", fontSize: 12, textDecoration: "none" }}
          >
            📄 PDF Report
          </a>
        )}

        <Link href="/dashboard" className="primary" style={{ padding: "6px 14px", fontSize: 12, textDecoration: "none" }}>
          Launch Command Center →
        </Link>
      </div>
    </header>
  );
}
