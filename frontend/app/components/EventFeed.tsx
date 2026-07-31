"use client";

type EventItem = {
  tier: number;
  action: string;
  target: string;
  kw: number;
  households: number;
  reason_code: string;
  detail?: string;
  t?: number;
};

interface EventFeedProps {
  events?: EventItem[];
  title?: string;
}

export default function EventFeed({ events = [], title = "Auditable Decision Feed" }: EventFeedProps) {
  const getTierClass = (tier: number) => {
    switch (tier) {
      case 1:
        return "tier-1";
      case 2:
        return "tier-2";
      case 3:
        return "tier-3";
      default:
        return "tier-0";
    }
  };

  const getTierName = (tier: number) => {
    switch (tier) {
      case 1:
        return "Tier 1: Steady State";
      case 2:
        return "Tier 2: Pre-emptive";
      case 3:
        return "Tier 3: Last Resort";
      default:
        return "Baseline / Trip";
    }
  };

  return (
    <div className="run-card" style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
        <div>
          <span className="kicker">REAL-TIME AUDIT LOG</span>
          <h4 style={{ margin: "2px 0 0", fontSize: 16 }}>{title}</h4>
        </div>
        <span style={{ fontSize: 11, color: "var(--muted)", fontWeight: "bold" }}>
          {events.length} {events.length === 1 ? "Event" : "Events"}
        </span>
      </div>

      {events.length === 0 ? (
        <div className="empty" style={{ flex: 1 }}>
          No intervention events recorded for this interval
        </div>
      ) : (
        <div className="event-feed" style={{ flex: 1 }}>
          {events.map((ev, idx) => (
            <div key={idx} className="event-item">
              <div className="event-item-header">
                <span className={`tier-badge ${getTierClass(ev.tier)}`}>
                  {getTierName(ev.tier)}
                </span>
                <span>Target: <strong>{ev.target}</strong></span>
              </div>
              <div style={{ margin: "4px 0", color: "var(--ink)", fontWeight: 500 }}>
                {ev.detail || `${ev.action} on ${ev.target} (${ev.kw.toFixed(1)} kW, ${ev.households} homes)`}
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "var(--muted)" }}>
                <span>Code: <code>{ev.reason_code}</code></span>
                {ev.kw > 0 && <span>Capacity: {ev.kw.toFixed(1)} kW</span>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
