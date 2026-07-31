import type { ArmSnapshot } from "../types";

type Props = {
  snapshot: ArmSnapshot;
  selectedDt: string;
  onSelect: (dtId: string) => void;
  activeTargets?: Set<string>;
  compact?: boolean;
};

function stateOf(loading: number, energized: boolean) {
  if (!energized) return "offline";
  if (loading >= 100) return "overloaded";
  if (loading >= 90) return "strained";
  return "stable";
}

export function TransformerGrid({ snapshot, selectedDt, onSelect, activeTargets = new Set(), compact = false }: Props) {
  const feeders = ["F1", "F2", "F3"];
  return (
    <div className={`transformer-grid ${compact ? "compact" : ""}`}>
      {feeders.map((feeder) => {
        const rows = snapshot.dts.filter((dt) => dt.id.startsWith(`${feeder}-`));
        return (
          <section className="feeder-group" key={feeder} aria-label={`${feeder} transformer states`}>
            <div className="feeder-label"><strong>{feeder}</strong><span>{snapshot.feeders.find((row) => row.id === feeder)?.loading_pct.toFixed(1)}%</span></div>
            <div className="dt-cells">
              {rows.map((dt) => {
                const state = stateOf(dt.loading_pct, dt.energized);
                const number = dt.id.slice(-2);
                return (
                  <button
                    type="button"
                    key={dt.id}
                    className={`dt-cell ${state} ${selectedDt === dt.id ? "selected" : ""} ${activeTargets.has(dt.id) ? "intervened" : ""}`}
                    onClick={() => onSelect(dt.id)}
                    aria-pressed={selectedDt === dt.id}
                    aria-label={`${dt.id}, ${dt.loading_pct.toFixed(1)} percent loaded, ${dt.energized ? "energised" : "off"}, ${dt.households_dark} homes dark`}
                  >
                    <span>{number}</span>
                    {!compact && <i style={{ height: `${Math.min(dt.loading_pct, 125) / 1.25}%` }} />}
                  </button>
                );
              })}
            </div>
          </section>
        );
      })}
    </div>
  );
}
