"use client";

import Navbar from "@/components/layout/Navbar";
import Sidebar from "@/components/layout/Sidebar";
import MetricsTable from "@/components/MetricsTable";
import TimelineScrubber from "@/components/TimelineScrubber";
import NetworkSchematic2D from "@/components/NetworkSchematic2D";
import { useSimulationStore } from "@/store/simulationStore";
import { ScenarioName } from "@/types";

export default function SimulationPage() {
  const {
    scenario,
    seed,
    amiPenetration,
    devicePenetration,
    evPenetration,
    busy,
    status,
    ticks,
    currentTickIndex,
    isPlaying,
    speed,
    summary,
    setScenario,
    setSeed,
    setAmiPenetration,
    setDevicePenetration,
    setEvPenetration,
    startSimulation,
    injectTrigger,
    setIsPlaying,
    setSpeed,
    setCurrentTickIndex,
  } = useSimulationStore();

  const currentTick = ticks[currentTickIndex] || null;
  const vidyutArm = currentTick?.arms?.vidyut;

  return (
    <div style={{ minHeight: "100vh" }}>
      <Navbar />

      <div style={{ display: "grid", gridTemplateColumns: "240px 1fr", gap: 24, padding: "24px 0" }}>
        <Sidebar />

        <div style={{ minWidth: 0 }}>
          <div className="heading" style={{ marginBottom: 20 }}>
            <div>
              <span className="kicker">SIMULATION CONSOLE</span>
              <h2>Grid Scenario &amp; Controllability Tuning</h2>
            </div>
            <p>Adjust scenario parameters, smart meter penetration, and trigger mid-run disruptions.</p>
          </div>

          {/* Scenario & Parameter Form */}
          <div className="run-card" style={{ marginBottom: 24 }}>
            <div className="card-title">
              <span>
                <small>SCENARIO SELECTION</small>
                <b>Simulation Parameters</b>
              </span>
              <em>STATUS: {status.toUpperCase()}</em>
            </div>

            <div className="fields">
              <label>
                Scenario
                <select value={scenario} onChange={(e) => setScenario(e.target.value as ScenarioName)} disabled={busy}>
                  <option value="heatwave">Heatwave (Peak Thermal Demand)</option>
                  <option value="ev_surge">EV Surge (Evening Cluster)</option>
                  <option value="normal">Normal Operating Day</option>
                </select>
              </label>

              <label>
                Random Seed
                <input type="number" value={seed} onChange={(e) => setSeed(Number(e.target.value))} disabled={busy} />
              </label>

              <label>
                Execute
                <button type="button" onClick={startSimulation} disabled={busy} className="primary">
                  {busy ? "Simulating..." : "▶ Run Simulation"}
                </button>
              </label>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 16, paddingTop: 16, borderTop: "1px solid var(--line)" }}>
              <label>
                Smart Meters (AMI): {(amiPenetration * 100).toFixed(0)}%
                <input type="range" min="0" max="1" step="0.05" value={amiPenetration} onChange={(e) => setAmiPenetration(Number(e.target.value))} disabled={busy} />
              </label>
              <label>
                Connected Devices: {(devicePenetration * 100).toFixed(0)}%
                <input type="range" min="0" max="1" step="0.05" value={devicePenetration} onChange={(e) => setDevicePenetration(Number(e.target.value))} disabled={busy} />
              </label>
              <label>
                EV Penetration: {(evPenetration * 100).toFixed(0)}%
                <input type="range" min="0" max="0.5" step="0.02" value={evPenetration} onChange={(e) => setEvPenetration(Number(e.target.value))} disabled={busy} />
              </label>
            </div>
          </div>

          {/* Judge Hotkeys */}
          <div className="judge-hotkeys">
            <label>JUDGE DISRUPTION TRIGGERS:</label>
            <button type="button" onClick={() => injectTrigger("heatwave", 1.2)} disabled={busy} className="hotkey-btn">
              <kbd>H</kbd> Heatwave (+20%)
            </button>
            <button type="button" onClick={() => injectTrigger("ev_surge", 1.5)} disabled={busy} className="hotkey-btn">
              <kbd>E</kbd> EV Surge (+50%)
            </button>
            <button type="button" onClick={() => injectTrigger("cloud_cover", 0.8)} disabled={busy} className="hotkey-btn">
              <kbd>C</kbd> Cloud Cover (-20%)
            </button>
            <button type="button" onClick={() => injectTrigger("dt_fault", 1.0)} disabled={busy} className="hotkey-btn">
              <kbd>F</kbd> DT Fault
            </button>
            <button type="button" onClick={() => startSimulation()} disabled={busy} className="hotkey-btn">
              <kbd>R</kbd> Reset Scenario
            </button>
          </div>

          {/* Live Grid Schematic */}
          <NetworkSchematic2D
            dts={vidyutArm?.dts}
            tieSwitches={vidyutArm?.topology?.tie_switches}
            title={`Active Simulation Grid — Tick ${currentTickIndex + 1} (${currentTick?.clock || "00:00"})`}
          />

          {/* Quantified Metrics Table */}
          <div className="run-card" style={{ marginBottom: 24 }}>
            <div className="card-title" style={{ marginBottom: 16 }}>
              <span>
                <small>SIMULATION SUMMARY</small>
                <b>Baseline vs Vidyut Cumulative Performance</b>
              </span>
            </div>
            <MetricsTable baseline={summary?.arms?.baseline} vidyut={summary?.arms?.vidyut} />
          </div>

          {/* Timeline Scrubber */}
          <TimelineScrubber
            currentTick={currentTickIndex}
            totalTicks={ticks.length || 96}
            isPlaying={isPlaying}
            speed={speed}
            clockTime={currentTick?.clock || "00:00"}
            onSeek={(t) => setCurrentTickIndex(t)}
            onTogglePlay={() => setIsPlaying(!isPlaying)}
            onSpeedChange={(s) => setSpeed(s)}
          />
        </div>
      </div>
    </div>
  );
}
