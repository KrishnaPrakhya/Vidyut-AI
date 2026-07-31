"use client";

import Navbar from "../../components/layout/Navbar";
import Sidebar from "../../components/layout/Sidebar";
import { API_URL } from "../../lib/constants";
import { useSimulationStore } from "../../store/simulationStore";

export default function SettingsPage() {
  const { seed, scenario, setSeed, setScenario } = useSimulationStore();

  return (
    <div style={{ minHeight: "100vh" }}>
      <Navbar />

      <div style={{ display: "grid", gridTemplateColumns: "240px 1fr", gap: 24, padding: "24px 0" }}>
        <Sidebar />

        <div style={{ minWidth: 0, maxWidth: 800 }}>
          <div className="heading">
            <div>
              <span className="kicker">SYSTEM PREFERENCES</span>
              <h2>System &amp; API Settings</h2>
            </div>
            <p>Configure default simulation seed, backend server endpoint, and execution preferences.</p>
          </div>

          <div style={{ display: "grid", gap: 24 }}>
            {/* Backend Connection */}
            <div className="run-card">
              <span className="kicker">BACKEND SERVER ENDPOINT</span>
              <h3 style={{ margin: "4px 0 16px", fontSize: 20 }}>FastAPI Server Configuration</h3>

              <div style={{ display: "grid", gap: 12 }}>
                <label>
                  API Base URL
                  <input type="text" value={API_URL} readOnly disabled style={{ background: "#f8fafc", color: "var(--muted)" }} />
                </label>
                <span style={{ fontSize: 11, color: "var(--muted)" }}>
                  Configured via environment variable <code>NEXT_PUBLIC_API_URL</code>.
                </span>
              </div>
            </div>

            {/* Default Parameters */}
            <div className="run-card">
              <span className="kicker">DEFAULT SCENARIO &amp; SEED</span>
              <h3 style={{ margin: "4px 0 16px", fontSize: 20 }}>Simulation Defaults</h3>

              <div className="fields" style={{ marginBottom: 0 }}>
                <label>
                  Default Scenario
                  <select value={scenario} onChange={(e) => setScenario(e.target.value as "heatwave" | "ev_surge" | "normal")}>
                    <option value="heatwave">Heatwave (Peak Demand)</option>
                    <option value="ev_surge">EV Surge</option>
                    <option value="normal">Normal Day</option>
                  </select>
                </label>

                <label>
                  Default Seed
                  <input type="number" value={seed} onChange={(e) => setSeed(Number(e.target.value))} />
                </label>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
