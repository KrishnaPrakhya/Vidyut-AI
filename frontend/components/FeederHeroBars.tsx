"use client";

type FeederData = {
  id: string;
  loading_pct: number;
  losses_kw: number;
};

interface FeederHeroBarsProps {
  baselineFeeders?: FeederData[];
  vidyutFeeders?: FeederData[];
}

export default function FeederHeroBars({
  baselineFeeders = [],
  vidyutFeeders = [],
}: FeederHeroBarsProps) {
  const feeders = ["F1", "F2", "F3"];

  const getFeederLoading = (list: FeederData[], id: string) => {
    const f = list.find((item) => item.id === id);
    return f ? f.loading_pct : 0;
  };

  const getStatusClass = (pct: number) => {
    if (pct > 100) return "critical";
    if (pct >= 90) return "warning";
    return "normal";
  };

  return (
    <div className="feeder-hero-card">
      <div className="feeder-hero-header">
        <div>
          <span className="kicker">THESIS VISUALIZATION</span>
          <h3 style={{ margin: "4px 0 0", fontSize: "20px" }}>
            Feeder Loading Distribution (Before vs After)
          </h3>
        </div>
        <div className="legend">
          <span style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <i style={{ width: 12, height: 12, background: "#486d2a", display: "inline-block" }} /> Vidyut
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <i style={{ width: 12, height: 12, background: "#667068", opacity: 0.6, display: "inline-block" }} /> Baseline
          </span>
        </div>
      </div>

      <div className="feeder-bars-container">
        {feeders.map((fId) => {
          const basePct = getFeederLoading(baselineFeeders, fId);
          const vidPct = getFeederLoading(vidyutFeeders, fId);
          return (
            <div key={fId} className="feeder-bar-group">
              <div className="feeder-bar-title">
                <span>FEEDER {fId}</span>
                <span>
                  <strong>{vidPct.toFixed(1)}%</strong> <small style={{ opacity: 0.7 }}>vs {basePct.toFixed(1)}%</small>
                </span>
              </div>
              
              {/* Vidyut Bar */}
              <div className="bar-track" title={`Vidyut Feeder ${fId}: ${vidPct.toFixed(1)}%`}>
                <div
                  className={`bar-fill ${getStatusClass(vidPct)}`}
                  style={{ width: `${Math.min(100, vidPct)}%` }}
                >
                  {vidPct > 15 ? `Vidyut: ${vidPct.toFixed(1)}%` : ""}
                </div>
              </div>

              {/* Baseline Bar */}
              <div className="bar-track" title={`Baseline Feeder ${fId}: ${basePct.toFixed(1)}%`}>
                <div
                  className="bar-fill baseline"
                  style={{ width: `${Math.min(100, basePct)}%`, background: basePct > 100 ? "#dc2626" : "#667068" }}
                >
                  {basePct > 15 ? `Baseline: ${basePct.toFixed(1)}%` : ""}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
