export type ScenarioName = "heatwave" | "ev_surge" | "normal";

export type DTData = {
  id: string;
  loading_pct: number;
  energized: boolean;
  households_dark: number;
};

export type FeederData = {
  id: string;
  loading_pct: number;
  losses_kw: number;
};

export type TieSwitchData = {
  id: string;
  closed: boolean;
};

export type EventItem = {
  tier: number;
  action: string;
  target: string;
  kw: number;
  households: number;
  reason_code: string;
  detail?: string;
  t?: number;
};

export type ArmTickData = {
  feeders: FeederData[];
  dts: DTData[];
  topology: { tie_switches: TieSwitchData[] };
  metrics: {
    converged: boolean;
    peak_kva: number;
    spread_pct: number;
    losses_kw: number;
    homes_dark: number;
    critical_uptime_pct: number;
    unserved_kwh: number;
    gini: number;
    max_trafo_loading_pct: number;
  };
  events: EventItem[];
};

export type ForecastData = {
  model: string;
  runtime_ready: boolean;
  dt_id: string;
  horizon_kw: number[];
  safe_limit_kw: number;
  rating_kw: number;
};

export type TickMessage = {
  type?: string;
  t: number;
  clock: string;
  arms: {
    baseline: ArmTickData;
    vidyut: ArmTickData;
  };
  forecast?: ForecastData | null;
};

export type SummaryData = {
  ready: boolean;
  arms: {
    baseline: Record<string, number>;
    vidyut: Record<string, number>;
  };
  deltas: Record<string, number>;
};

export type OfflineFixture = {
  ticks: TickMessage[];
  summary: SummaryData;
};
