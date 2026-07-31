"use client";

import { useState } from "react";

type DTData = {
  id: string;
  loading_pct: number;
  energized: boolean;
  households_dark: number;
};

type TieSwitchData = {
  id: string;
  closed: boolean;
};

interface NetworkSchematic2DProps {
  dts?: DTData[];
  tieSwitches?: TieSwitchData[];
  title?: string;
}

export default function NetworkSchematic2D({
  dts = [],
  tieSwitches = [],
  title = "2D Grid Schematic (60 DTs, 3 Feeders)",
}: NetworkSchematic2DProps) {
  const [hoveredNode, setHoveredNode] = useState<DTData | null>(null);

  const dtMap = new Map<string, DTData>();
  dts.forEach((d) => dtMap.set(d.id, d));

  const getColor = (dt?: DTData) => {
    if (!dt || !dt.energized) return "#64748b"; // Grey de-energized
    if (dt.loading_pct > 100) return "#ef4444"; // Red overloaded
    if (dt.loading_pct >= 90) return "#f59e0b"; // Amber warning
    return "#22c55e"; // Green normal
  };

  const feeders = [
    { id: "F1", x: 140 },
    { id: "F2", x: 400 },
    { id: "F3", x: 660 },
  ];

  return (
    <div className="schematic-card">
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
        <div>
          <span className="kicker" style={{ color: "#94a3b8" }}>TOPOLOGY VIEW</span>
          <h4 style={{ margin: "2px 0 0", color: "#f8fafc", fontSize: 16 }}>{title}</h4>
        </div>
        <div style={{ display: "flex", gap: 12, fontSize: 10 }}>
          <span style={{ color: "#22c55e" }}>● &lt;90%</span>
          <span style={{ color: "#f59e0b" }}>● 90-100%</span>
          <span style={{ color: "#ef4444" }}>● &gt;100%</span>
          <span style={{ color: "#64748b" }}>● Off</span>
        </div>
      </div>

      <div style={{ position: "relative" }}>
        <svg viewBox="0 0 800 370" className="schematic-svg">
          {/* Substation */}
          <rect x="360" y="10" width="80" height="24" rx="4" fill="#0f172a" stroke="#38bdf8" strokeWidth="2" />
          <text x="400" y="26" textAnchor="middle" fill="#38bdf8" fontSize="10" fontWeight="bold" fontFamily="monospace">
            SUBSTATION
          </text>

          {/* Feeder Lines */}
          {feeders.map((f) => (
            <g key={f.id}>
              {/* Main Spine */}
              <line x1="400" y1="34" x2={f.x} y2="65" stroke="#475569" strokeWidth="2" />
              <line x1={f.x} y1="65" x2={f.x} y2="315" stroke="#475569" strokeWidth="2" />
              <text x={f.x} y="58" textAnchor="middle" fill="#94a3b8" fontSize="11" fontWeight="bold" fontFamily="monospace">
                FEEDER {f.id}
              </text>

              {/* 20 DT Nodes per feeder */}
              {Array.from({ length: 20 }).map((_, idx) => {
                const dtId = `${f.id}-DT${String(idx + 1).padStart(2, "0")}`;
                const dt = dtMap.get(dtId);
                const isRight = idx % 2 === 1;
                const row = Math.floor(idx / 2);
                const nx = f.x + (isRight ? 32 : -32);
                const ny = 78 + row * 23;

                return (
                  <g key={dtId} onMouseEnter={() => setHoveredNode(dt || null)} onMouseLeave={() => setHoveredNode(null)}>
                    <line x1={f.x} y1={ny} x2={nx} y2={ny} stroke="#334155" strokeWidth="1" />
                    <circle
                      cx={nx}
                      cy={ny}
                      r="7"
                      fill={getColor(dt)}
                      stroke="#0f172a"
                      strokeWidth="1.5"
                      style={{ cursor: "pointer" }}
                    />
                  </g>
                );
              })}
            </g>
          ))}

          {/* Tie Switches */}
          {/* TS-F1-F2 */}
          {(() => {
            const ts = tieSwitches.find((s) => s.id === "TS-F1-F2" || s.id === "TS-1");
            const closed = ts?.closed ?? false;
            return (
              <g>
                <line x1="140" y1="315" x2="400" y2="315" stroke={closed ? "#38bdf8" : "#475569"} strokeWidth={closed ? "2.5" : "1.5"} strokeDasharray={closed ? "none" : "4,4"} />
                <rect x="255" y="306" width="30" height="18" rx="3" fill={closed ? "#0284c7" : "#1e293b"} stroke={closed ? "#38bdf8" : "#64748b"} />
                <text x="270" y="318" textAnchor="middle" fill="#fff" fontSize="8" fontWeight="bold" fontFamily="monospace">
                  {closed ? "CLOSED" : "TS1-2"}
                </text>
              </g>
            );
          })()}

          {/* TS-F2-F3 */}
          {(() => {
            const ts = tieSwitches.find((s) => s.id === "TS-F2-F3" || s.id === "TS-2");
            const closed = ts?.closed ?? false;
            return (
              <g>
                <line x1="400" y1="315" x2="660" y2="315" stroke={closed ? "#38bdf8" : "#475569"} strokeWidth={closed ? "2.5" : "1.5"} strokeDasharray={closed ? "none" : "4,4"} />
                <rect x="515" y="306" width="30" height="18" rx="3" fill={closed ? "#0284c7" : "#1e293b"} stroke={closed ? "#38bdf8" : "#64748b"} />
                <text x="530" y="318" textAnchor="middle" fill="#fff" fontSize="8" fontWeight="bold" fontFamily="monospace">
                  {closed ? "CLOSED" : "TS2-3"}
                </text>
              </g>
            );
          })()}

          {/* TS-F1-F3 (Curved bottom line) */}
          {(() => {
            const ts = tieSwitches.find((s) => s.id === "TS-F1-F3" || s.id === "TS-3");
            const closed = ts?.closed ?? false;
            return (
              <g>
                <path d="M 140 315 Q 400 370 660 315" fill="none" stroke={closed ? "#38bdf8" : "#475569"} strokeWidth={closed ? "2.5" : "1.5"} strokeDasharray={closed ? "none" : "4,4"} />
                <rect x="385" y="340" width="30" height="18" rx="3" fill={closed ? "#0284c7" : "#1e293b"} stroke={closed ? "#38bdf8" : "#64748b"} />
                <text x="400" y="352" textAnchor="middle" fill="#fff" fontSize="8" fontWeight="bold" fontFamily="monospace">
                  {closed ? "CLOSED" : "TS1-3"}
                </text>
              </g>
            );
          })()}
        </svg>

        {hoveredNode && (
          <div
            style={{
              position: "absolute",
              bottom: 10,
              right: 10,
              background: "rgba(15, 23, 42, 0.95)",
              border: "1px solid #334155",
              padding: "8px 12px",
              borderRadius: 4,
              fontSize: 11,
              fontFamily: "monospace",
              color: "white",
            }}
          >
            <div><strong>DT ID:</strong> {hoveredNode.id}</div>
            <div><strong>Status:</strong> {hoveredNode.energized ? "ENERGIZED" : "DE-ENERGISED"}</div>
            <div><strong>Loading:</strong> {hoveredNode.loading_pct.toFixed(1)}%</div>
            {hoveredNode.households_dark > 0 && (
              <div style={{ color: "#ef4444" }}><strong>Homes Dark:</strong> {hoveredNode.households_dark}</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
