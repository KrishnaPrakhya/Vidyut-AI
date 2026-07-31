import { API_URL } from "../lib/constants";
import { SummaryData } from "../types";

export async function checkHealth() {
  const res = await fetch(`${API_URL}/api/health`);
  if (!res.ok) throw new Error("Health check failed");
  return res.json();
}

export async function createRun(payload: {
  scenario: string;
  seed: number;
  ticks?: number;
  carry_debt?: boolean;
  params?: Record<string, number>;
}) {
  const res = await fetch(`${API_URL}/api/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => null);
    throw new Error(errData?.detail || `Run creation failed with ${res.status}`);
  }
  return res.json(); // { run_id, status }
}

export async function getRunStatus(runId: string) {
  const res = await fetch(`${API_URL}/api/runs/${runId}`);
  if (!res.ok) throw new Error("Get run failed");
  return res.json();
}

export async function getRunSummary(runId: string): Promise<SummaryData> {
  const res = await fetch(`${API_URL}/api/runs/${runId}/summary`);
  if (!res.ok) throw new Error("Get run summary failed");
  return res.json();
}

export async function injectDisruption(runId: string, type: string, magnitude = 1.0, fromTick = 0) {
  const res = await fetch(`${API_URL}/api/runs/${runId}/inject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type, magnitude, from_tick: fromTick }),
  });
  if (!res.ok) throw new Error("Disruption injection failed");
  return res.json();
}

export async function getModelsArtifacts() {
  const res = await fetch(`${API_URL}/api/models`);
  if (!res.ok) throw new Error("Failed to fetch model artifacts");
  return res.json();
}

export async function getObservabilityStatus() {
  const res = await fetch(`${API_URL}/api/observability/status`);
  if (!res.ok) throw new Error("Failed to fetch observability status");
  return res.json();
}
