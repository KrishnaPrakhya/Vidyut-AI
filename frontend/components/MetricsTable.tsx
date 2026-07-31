"use client";

type ArmTotals = Record<string, number>;

interface MetricsTableProps {
  baseline?: ArmTotals;
  vidyut?: ArmTotals;
}

function fmt(val?: number, digits = 1): string {
  if (val === undefined || val === null || !Number.isFinite(val)) return "—";
  return new Intl.NumberFormat("en-IN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(val);
}

export default function MetricsTable({ baseline = {}, vidyut = {} }: MetricsTableProps) {
  const rows = [
    { key: "served_kwh", label: "Energy delivered kWh", digits: 0, invertDelta: false },
    { key: "flexibility_kwh", label: "Demand flexibility kWh", digits: 1, invertDelta: false },
    { key: "unserved_kwh", label: "Unserved energy kWh", digits: 1, invertDelta: true },
    { key: "unserved_cost_rs", label: "Unserved energy cost ₹", digits: 0, invertDelta: true },
    { key: "peak_homes_dark", label: "Homes dark, peak count", digits: 0, invertDelta: true },
    { key: "homes_dark_minutes", label: "Homes dark, household-minutes", digits: 0, invertDelta: true },
    { key: "critical_uptime_pct", label: "Critical-load uptime %", digits: 3, invertDelta: false },
    { key: "max_trafo_loading_pct", label: "Max transformer loading %", digits: 1, invertDelta: true },
    { key: "mean_spread_pct", label: "Feeder spread, mean %", digits: 1, invertDelta: true },
    { key: "losses_pct_of_delivered", label: "Network losses (% of delivered)", digits: 2, invertDelta: true },
    { key: "households_curtailed", label: "Households affected", digits: 0, invertDelta: false },
    { key: "gini", label: "Curtailment Gini (all households)", digits: 4, invertDelta: true },
    { key: "nonconverged_ticks", label: "Non-converged ticks (grid collapse)", digits: 0, invertDelta: true },
  ];

  return (
    <div className="metric-table">
      <div className="metric-head">
        <span>PERFORMANCE METRIC</span>
        <span style={{ textAlign: "right" }}>BASELINE</span>
        <span style={{ textAlign: "right" }}>VIDYUT</span>
        <span style={{ textAlign: "right" }}>DELTA</span>
      </div>

      {rows.map((r) => {
        const bVal = baseline[r.key];
        const vVal = vidyut[r.key];
        const hasVals = bVal !== undefined && vVal !== undefined;
        const delta = hasVals ? vVal - bVal : 0;
        
        let deltaClass = "";
        if (hasVals && Math.abs(delta) > 1e-4) {
          const isGood = r.invertDelta ? delta < 0 : delta > 0;
          deltaClass = isGood ? "good" : "bad";
        }

        return (
          <div key={r.key} className="metric-row">
            <div>
              <strong>{r.label}</strong>
            </div>
            <div style={{ textAlign: "right" }}>{fmt(bVal, r.digits)}</div>
            <div style={{ textAlign: "right" }}>{fmt(vVal, r.digits)}</div>
            <div style={{ textAlign: "right" }} className={deltaClass}>
              {hasVals ? (delta > 0 ? `+${fmt(delta, r.digits)}` : fmt(delta, r.digits)) : "—"}
            </div>
          </div>
        );
      })}
    </div>
  );
}
