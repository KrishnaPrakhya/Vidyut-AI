"use client";

interface AlertPanelProps {
  maxLoading?: number;
  unservedKwh?: number;
  nonconverged?: number;
}

export default function AlertPanel({ maxLoading = 0, unservedKwh = 0, nonconverged = 0 }: AlertPanelProps) {
  return (
    <div className="run-card" style={{ height: "100%" }}>
      <span className="kicker">GRID MONITORING & ALERTS</span>
      <h4 style={{ margin: "4px 0 12px", fontSize: 16 }}>Live Contingency Alert Panel</h4>

      <div style={{ display: "grid", gap: 10 }}>
        {maxLoading > 100 ? (
          <div className="alert" style={{ margin: 0, padding: "8px 12px", background: "#fee2e2", borderColor: "#ef4444", color: "#b91c1c" }}>
            🚨 <strong>CRITICAL OVERLOAD:</strong> Distribution Transformer loading exceeded 100% ({maxLoading.toFixed(1)}%).
          </div>
        ) : maxLoading >= 90 ? (
          <div className="alert" style={{ margin: 0, padding: "8px 12px", background: "#fef3c7", borderColor: "#f59e0b", color: "#b45309" }}>
            ⚠️ <strong>HIGH THERMAL LOAD:</strong> Transformer loading in warning zone ({maxLoading.toFixed(1)}%). Pre-emptive Tier 2 active.
          </div>
        ) : (
          <div style={{ padding: "8px 12px", background: "#dcfce7", border: "1px solid #22c55e", color: "#15803d", fontSize: 13 }}>
            ✅ <strong>GRID STABLE:</strong> Transformer loading within safe thermal headroom limits ({maxLoading.toFixed(1)}%).
          </div>
        )}

        {unservedKwh > 0 && (
          <div style={{ padding: "8px 12px", background: "#fff1e9", border: "1px solid #d28563", color: "#7b3116", fontSize: 12 }}>
            ℹ️ Unserved demand accumulated: {unservedKwh.toFixed(1)} kWh
          </div>
        )}

        {nonconverged > 0 && (
          <div style={{ padding: "8px 12px", background: "#fee2e2", border: "1px solid #ef4444", color: "#b91c1c", fontSize: 12 }}>
            💥 Power flow non-convergence detected (Baseline voltage collapse).
          </div>
        )}
      </div>
    </div>
  );
}
