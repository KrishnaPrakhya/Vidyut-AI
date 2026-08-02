import type { ScenarioName } from "../types";

export type Preferences = {
  scenario: ScenarioName;
  replayMs: number;
};

export const PREFERENCES_KEY = "vidyut.preferences";

export const DEFAULT_PREFERENCES: Preferences = { scenario: "heatwave", replayMs: 650 };

export const REPLAY_SPEEDS = [
  { ms: 1200, label: "Slow · 1.2s per interval" },
  { ms: 650, label: "Standard · 0.65s per interval" },
  { ms: 320, label: "Fast · 0.32s per interval" },
] as const;

const SCENARIOS: ScenarioName[] = ["normal", "heatwave", "ev_surge"];

export function readPreferences(): Preferences {
  if (typeof window === "undefined") return DEFAULT_PREFERENCES;
  try {
    const raw = window.localStorage.getItem(PREFERENCES_KEY);
    if (!raw) return DEFAULT_PREFERENCES;
    const parsed = JSON.parse(raw) as Partial<Preferences>;
    return {
      scenario: SCENARIOS.includes(parsed.scenario as ScenarioName) ? parsed.scenario as ScenarioName : DEFAULT_PREFERENCES.scenario,
      replayMs: REPLAY_SPEEDS.some((speed) => speed.ms === parsed.replayMs) ? parsed.replayMs as number : DEFAULT_PREFERENCES.replayMs,
    };
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

export function writePreferences(next: Preferences): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(PREFERENCES_KEY, JSON.stringify(next));
}

export function clearPreferences(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(PREFERENCES_KEY);
}

export function storedPreferences(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(PREFERENCES_KEY);
}
