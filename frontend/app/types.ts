export type ArmName = "baseline" | "vidyut";
export type ScenarioName = "normal" | "heatwave" | "ev_surge";

export type TickEvent = {
  tier: number;
  action: string;
  target: string;
  kw: number;
  households: number;
  reason_code: string;
  detail: string;
  forecast_kw: number | null;
  safe_limit_kw: number | null;
};

export type FeederSnapshot = {
  id: string;
  loading_pct: number;
  losses_kw: number;
};

export type DtSnapshot = {
  id: string;
  loading_pct: number;
  energized: boolean;
  households_dark: number;
};

export type ArmMetrics = {
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

export type ArmSnapshot = {
  feeders: FeederSnapshot[];
  dts: DtSnapshot[];
  topology: { tie_switches: Array<{ id: string; closed: boolean }> };
  metrics: ArmMetrics;
  events: TickEvent[];
};

export type ForecastSnapshot = {
  model: string;
  runtime_ready: boolean;
  dt_id: string;
  horizon_kw: number[];
  safe_limit_kw: number;
  rating_kw: number;
};

export type TickFrame = {
  t: number;
  clock: string;
  arms: Record<ArmName, ArmSnapshot>;
  forecast: ForecastSnapshot | null;
};

export type RunTotals = {
  arm: ArmName;
  peak_kva: number;
  max_trafo_loading_pct: number;
  total_losses_kwh: number;
  mean_spread_pct: number;
  max_spread_pct: number;
  homes_dark_minutes: number;
  peak_homes_dark: number;
  critical_uptime_pct: number;
  unserved_kwh: number;
  demanded_kwh: number;
  flexibility_kwh: number;
  energy_balance_error_kwh: number;
  unserved_cost_rs: number;
  served_kwh: number;
  losses_pct_of_delivered: number;
  gini: number;
  gini_affected: number;
  max_household_burden_min: number;
  households_curtailed: number;
  nonconverged_ticks: number;
  addressable_share_of_load: number;
  minutes_by_level: Record<string, number>;
  events_by_tier: Record<string, number>;
  spread_series: number[];
};

export type Recording = {
  meta: {
    schema_version: number;
    scenario: ScenarioName;
    seed: number;
    ticks: number;
    arms: ArmName[];
    simulated: boolean;
  };
  ticks: TickFrame[];
  summary: {
    arms: Record<ArmName, RunTotals>;
    deltas: Record<string, number>;
  };
  notifications: Notification[];
};

export type Notification = {
  tick: number;
  clock: string;
  channel: string;
  event_type: string;
  dt_id: string;
  feeder_id: string;
  households: number;
  reason_code: string;
  message: string;
  tariff_multiplier: number | null;
  expected_reduction_kw: number | null;
  window_minutes: number | null;
};

export type StoryBeat = {
  id: string;
  tick: number;
  label: string;
  title: string;
  body: string;
  kind: "heat" | "overload" | "outage" | "forecast" | "control" | "protected" | "outcome";
  focusDt: string | null;
  primary: string;
  secondary: string;
};

export type RunRecord = {
  run_id: string;
  scenario: ScenarioName;
  seed: number;
  ticks: number;
  status: "pending" | "running" | "ready" | "failed";
  error: string | null;
  generation: number;
  persisted: boolean;
};

export type RunFlexibility = {
  registered: {
    capacity_kw: number;
    households: number;
    devices: number;
    capacity_by_kind_kw: Record<string, number>;
    source: string;
  };
  available: {
    profile_kw: number[];
    peak_kw: number;
    energy_kwh: number;
    source: string;
  };
  realised: {
    reduction_kwh: number;
    source: string;
  };
};

export type RunSummary = RunRecord & {
  ready: boolean;
  arms: Record<ArmName, RunTotals>;
  deltas: Record<string, number>;
};

export type OpportunityEstimate = {
  ready: boolean;
  reasons: string[];
  estimated_profile_kw: number[];
  actionable_profile_kw: number[] | null;
  estimated_average_kw: number;
  estimated_peak_kw: number;
  estimated_aggregate_share: number;
  actionable_average_kw: number | null;
  actionable_peak_kw: number | null;
  registered_capacity_kw: number | null;
  confidence: string;
  coverage_pct: number;
  temperature_span_c: number;
  fit_score: number;
  source: "estimated";
  method: string;
};

export type VerificationResult = {
  ready: boolean;
  method: string;
  selected_days: number[];
  baseline_profile_kw: number[];
  observed_profile_kw: number[];
  baseline_average_kw: number;
  observed_average_kw: number;
  gross_difference_kw: number;
  realised_reduction_kw: number;
  realised_reduction_kwh: number;
  committed_reduction_kw: number;
  performance_pct: number | null;
  same_day_adjustment_kw: number;
  coverage_pct: number;
  confidence: string;
  source: "verified";
};

export type FairnessRow = {
  household_id: string;
  dt_id: string;
  cumulative_debt_min: number;
  minutes_by_level: Record<string, number>;
  last_curtailed_at: string | null;
};

export type ForecastEvaluation = {
  trained: boolean;
  runtime_ready: boolean;
  evaluation_only: boolean;
  runtime_message: string;
  holdout: string;
  n_series: number;
  n_obs: number;
  models: Record<string, { MASE: number; MAPE?: number }>;
  cold_start: {
    history_days: number;
    lgbm_from_scratch: { MASE: number };
    chronos_finetuned: { MASE: number };
  };
  by_horizon: Record<string, Record<string, { MASE: number; MAPE: number; MAE_kw: number }>>;
  data: {
    country: string;
    real_measurements: boolean;
    synthetic_training_data: boolean;
    sources: string[];
  };
};

export type ModelsRegistry = {
  any_trained: boolean;
  models: { forecast: ForecastEvaluation };
};
