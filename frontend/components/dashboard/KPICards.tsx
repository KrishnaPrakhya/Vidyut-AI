"use client";

import { formatNumber } from "../../lib/helpers";

interface KPICardsProps {
  baseline?: Record<string, number>;
  vidyut?: Record<string, number>;
}

export default function KPICards({ baseline = {}, vidyut = {} }: KPICardsProps) {
  const kpis = [
    {
      title: "ENERGY DELIVERED",
      vidyutVal: vidyut.served_kwh,
      baselineVal: baseline.served_kwh,
      unit: "kWh",
      goodIfHigh: true,
    },
    {
      title: "UNSERVED ENERGY",
      vidyutVal: vidyut.unserved_kwh,
      baselineVal: baseline.unserved_kwh,
      unit: "kWh",
      goodIfHigh: false,
    },
    {
      title: "CRITICAL UPTIME",
      vidyutVal: vidyut.critical_uptime_pct,
      baselineVal: baseline.critical_uptime_pct,
      unit: "%",
      goodIfHigh: true,
    },
    {
      title: "MAX TRAFO LOADING",
      vidyutVal: vidyut.max_trafo_loading_pct,
      baselineVal: baseline.max_trafo_loading_pct,
      unit: "%",
      goodIfHigh: false,
    },
  ];

  return (
    <div className="kpi-grid">
      {kpis.map((kpi, idx) => {
        const delta = (kpi.vidyutVal ?? 0) - (kpi.baselineVal ?? 0);
        const isGood = kpi.goodIfHigh ? delta > 0 : delta < 0;
        return (
          <div key={idx} className="kpi-card">
            <span className="kicker">{kpi.title}</span>
            <div className="kpi-value">
              {formatNumber(kpi.vidyutVal, 1)} <small>{kpi.unit}</small>
            </div>
            <div className="kpi-baseline">
              Baseline: {formatNumber(kpi.baselineVal, 1)} {kpi.unit} |{" "}
              <span className={isGood ? "good" : "bad"}>
                Delta: {delta > 0 ? `+${formatNumber(delta, 1)}` : formatNumber(delta, 1)}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
