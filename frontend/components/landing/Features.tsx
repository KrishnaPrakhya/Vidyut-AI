"use client";

export default function Features() {
  const features = [
    {
      title: "Pre-Emptive Thermal Headroom",
      desc: "4-tick horizon forecasting detects upcoming transformer overload before it occurs, initiating device-level curtailment.",
      tag: "TIER 2 CONTROL",
    },
    {
      title: "Feeder Reconfiguration",
      desc: "Baran & Wu (1989) branch-exchange heuristic optimizes open tie-switches to balance load spread across feeders.",
      tag: "TIER 1 TOPOLOGY",
    },
    {
      title: "Equity & Fairness Ledger",
      desc: "Tracks cumulative household curtailment debt to ensure interventions are distributed fairly across neighbors.",
      tag: "FAIRNESS LEDGER",
    },
    {
      title: "Per-Household Auditability",
      desc: "Every intervention carries a machine-generated, human-readable reason code explaining why and for how long.",
      tag: "AUDIT LOG",
    },
  ];

  return (
    <section className="block">
      <div className="heading">
        <div>
          <span className="kicker">SYSTEM CAPABILITIES</span>
          <h2>Key Features</h2>
        </div>
        <p>Four key innovations solving distribution transformer overloads while maintaining fairness.</p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 20 }}>
        {features.map((f, idx) => (
          <div key={idx} className="run-card">
            <span className="kicker">{f.tag}</span>
            <h3 style={{ margin: "8px 0 10px", fontSize: 20 }}>{f.title}</h3>
            <p style={{ fontSize: 14, color: "var(--muted)", lineHeight: 1.5 }}>{f.desc}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
