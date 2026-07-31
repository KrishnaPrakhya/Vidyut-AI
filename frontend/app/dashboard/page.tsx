"use client";

import { useEffect } from "react";
import Navbar from "@/components/layout/Navbar";
import Sidebar from "@/components/layout/Sidebar";
import KPICards from "@/components/dashboard/KPICards";
import AlertPanel from "@/components/dashboard/AlertPanel";
import NetworkSchematic2D from "@/components/NetworkSchematic2D";
import ForecastChart from "@/components/ForecastChart";
import EventFeed from "@/components/EventFeed";
import TimelineScrubber from "@/components/TimelineScrubber";
import FeederHeroBars from "@/components/FeederHeroBars";
import { useSimulationStore } from "@/store/simulationStore";

export default function DashboardPage() {
  const {
    ticks,
    currentTickIndex,
    isPlaying,
    speed,
    summary,
    startSimulation,
    setIsPlaying,
    setSpeed,
    setCurrentTickIndex,
    injectTrigger,
  } = useSimulationStore();

  useEffect(() => {
    if (ticks.length === 0) {
      startSimulation();
    }
  }, [ticks.length, startSimulation]);

  const currentTick = ticks[currentTickIndex] || null;
  const vidyutArm = currentTick?.arms?.vidyut;
  const baselineArm = currentTick?.arms?.baseline;

  return (
    <div style={{ minHeight: "100vh" }}>
      <Navbar />

      <div style={{ display: "grid", gridTemplateColumns: "240px 1fr", gap: 24, padding: "24px 0" }}>
        {/* Sidebar */}
        <Sidebar />

        {/* Main Workspace */}
        <div style={{ minWidth: 0 }}>
          {/* Header Title */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
            <div>
              <span className="kicker">AI COMMAND CENTER</span>
              <h2 style={{ margin: "2px 0 0", fontSize: 28 }}>Grid Operating Dashboard</h2>
            </div>

            <div style={{ display: "flex", gap: 8 }}>
              <button type="button" onClick={() => injectTrigger("heatwave", 1.2)} className="hotkey-btn">
                <kbd>H</kbd> Heatwave
              </button>
              <button type="button" onClick={() => injectTrigger("ev_surge", 1.5)} className="hotkey-btn">
                <kbd>E</kbd> EV Surge
              </button>
              <button type="button" onClick={() => injectTrigger("dt_fault", 1.0)} className="hotkey-btn">
                <kbd>F</kbd> DT Fault
              </button>
            </div>
          </div>

          {/* Top KPI Cards */}
          <div style={{ marginBottom: 24 }}>
            <KPICards baseline={summary?.arms?.baseline} vidyut={summary?.arms?.vidyut} />
          </div>

          {/* Thesis Feeder Hero Bars */}
          <FeederHeroBars
            baselineFeeders={baselineArm?.feeders}
            vidyutFeeders={vidyutArm?.feeders}
          />

          {/* Twin Grid Visualization (Main Hero): Baseline Grid | Vidyut Grid */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 24 }}>
            <NetworkSchematic2D
              dts={baselineArm?.dts}
              tieSwitches={baselineArm?.topology?.tie_switches}
              title={`Baseline Grid (Current Practice) — Tick ${currentTickIndex + 1}`}
            />

            <NetworkSchematic2D
              dts={vidyutArm?.dts}
              tieSwitches={vidyutArm?.topology?.tie_switches}
              title={`Vidyut AI Balanced Grid — Tick ${currentTickIndex + 1}`}
            />
          </div>

          {/* Forecast Graph | AI Decision Feed | Alert Panel */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1.1fr 0.9fr", gap: 20, marginBottom: 24 }}>
            <ForecastChart forecast={currentTick?.forecast} />
            <EventFeed events={vidyutArm?.events} title="AI Decision Feed (Tier 1–3)" />
            <AlertPanel
              maxLoading={vidyutArm?.metrics?.max_trafo_loading_pct || 0}
              unservedKwh={vidyutArm?.metrics?.unserved_kwh || 0}
              nonconverged={baselineArm?.metrics?.converged === false ? 1 : 0}
            />
          </div>

          {/* Timeline Scrubber & Playback Controls */}
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
