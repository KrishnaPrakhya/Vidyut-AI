"use client";

type ForecastData = {
  model: string;
  runtime_ready: boolean;
  dt_id: string;
  horizon_kw: number[];
  safe_limit_kw: number;
  rating_kw: number;
};

interface ForecastChartProps {
  forecast?: ForecastData | null;
}

export default function ForecastChart({ forecast }: ForecastChartProps) {
  if (!forecast || !forecast.horizon_kw || forecast.horizon_kw.length === 0) {
    return (
      <div className="run-card" style={{ height: "100%", minHeight: 220 }}>
        <span className="kicker">PRE-EMPTIVE ASSURANCE</span>
        <h4 style={{ margin: "4px 0 12px", fontSize: 16 }}>Horizon Forecast vs Headroom</h4>
        <div className="empty">No active transformer forecast threshold breach</div>
      </div>
    );
  }

  const { dt_id, horizon_kw, safe_limit_kw, rating_kw } = forecast;
  const maxKw = Math.max(...horizon_kw, safe_limit_kw, rating_kw, 1);
  const safePct = (safe_limit_kw / maxKw) * 100;
  const ratingPct = (rating_kw / maxKw) * 100;

  return (
    <div className="run-card" style={{ height: "100%" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
        <div>
          <span className="kicker">PRE-EMPTIVE ASSURANCE (TIER 2)</span>
          <h4 style={{ margin: "4px 0 0", fontSize: 16 }}>
            Forecast Headroom: {dt_id}
          </h4>
        </div>
        <em style={{ font: "700 9px monospace", background: "#edf8d3", color: "#426f24", padding: "4px 6px" }}>
          {forecast.model}
        </em>
      </div>

      <div style={{ margin: "12px 0", fontSize: 11, color: "var(--muted)", display: "flex", gap: 16 }}>
        <span>Safe Limit: <strong>{safe_limit_kw.toFixed(1)} kW</strong> (90%)</span>
        <span>Rating: <strong>{rating_kw.toFixed(1)} kW</strong></span>
      </div>

      {/* Chart Canvas */}
      <div style={{ position: "relative", height: 130, borderBottom: "1px solid #c8cec3", display: "flex", alignItems: "flex-end", gap: 12, paddingBottom: 4 }}>
        {/* Rating Line */}
        <div
          style={{
            position: "absolute",
            bottom: `${ratingPct}%`,
            left: 0,
            right: 0,
            borderTop: "1px dashed #dc2626",
            zIndex: 1,
          }}
          title={`Rating: ${rating_kw} kW`}
        >
          <span style={{ position: "absolute", right: 0, top: -14, fontSize: 9, color: "#dc2626", fontWeight: "bold" }}>
            Rating ({rating_kw.toFixed(0)}kW)
          </span>
        </div>

        {/* Safe Limit Line */}
        <div
          style={{
            position: "absolute",
            bottom: `${safePct}%`,
            left: 0,
            right: 0,
            borderTop: "2px solid #d97706",
            zIndex: 2,
          }}
          title={`Safe Limit: ${safe_limit_kw} kW`}
        >
          <span style={{ position: "absolute", left: 0, top: -14, fontSize: 9, color: "#d97706", fontWeight: "bold" }}>
            Safe Threshold ({safe_limit_kw.toFixed(0)}kW)
          </span>
        </div>

        {/* Bars for 4 ticks */}
        {horizon_kw.map((kw, idx) => {
          const heightPct = (kw / maxKw) * 100;
          const isBreach = kw > safe_limit_kw;
          return (
            <div key={idx} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", height: "100%", justifyContent: "flex-end", zIndex: 3 }}>
              <span style={{ fontSize: 10, fontWeight: "bold", color: isBreach ? "#dc2626" : "var(--ink)", marginBottom: 2 }}>
                {kw.toFixed(1)} kW
              </span>
              <div
                style={{
                  width: "100%",
                  maxWidth: 36,
                  height: `${heightPct}%`,
                  background: isBreach ? "#dc2626" : "#486d2a",
                  borderRadius: "2px 2px 0 0",
                  transition: "height 0.3s ease",
                }}
              />
              <span style={{ fontSize: 9, color: "var(--muted)", marginTop: 4 }}>
                +{ (idx + 1) * 15 }m
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
