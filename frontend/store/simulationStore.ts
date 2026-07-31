import { create } from "zustand";
import { ScenarioName, TickMessage, SummaryData } from "../types";
import { createRun, getRunStatus, getRunSummary, injectDisruption } from "../services/api";
import { connectSimulationWebSocket } from "../services/websocket";

interface SimulationState {
  scenario: ScenarioName;
  seed: number;
  amiPenetration: number;
  devicePenetration: number;
  evPenetration: number;
  runId: string | null;
  status: string;
  busy: boolean;
  error: string | null;
  offlineMode: boolean;

  ticks: TickMessage[];
  currentTickIndex: number;
  isPlaying: boolean;
  speed: number;
  summary: SummaryData | null;

  setScenario: (scenario: ScenarioName) => void;
  setSeed: (seed: number) => void;
  setAmiPenetration: (val: number) => void;
  setDevicePenetration: (val: number) => void;
  setEvPenetration: (val: number) => void;
  setSpeed: (speed: number) => void;
  setIsPlaying: (playing: boolean) => void;
  setCurrentTickIndex: (index: number) => void;
  setOfflineMode: (offline: boolean) => void;

  startSimulation: () => Promise<void>;
  injectTrigger: (type: string, magnitude?: number) => Promise<void>;
  loadOfflineFixture: (scen: string, sd: number) => Promise<void>;
}

let activeWs: WebSocket | null = null;

export const useSimulationStore = create<SimulationState>((set, get) => ({
  scenario: "heatwave",
  seed: 42,
  amiPenetration: 0.55,
  devicePenetration: 0.25,
  evPenetration: 0.08,
  runId: null,
  status: "idle",
  busy: false,
  error: null,
  offlineMode: false,

  ticks: [],
  currentTickIndex: 0,
  isPlaying: false,
  speed: 4,
  summary: null,

  setScenario: (scenario) => set({ scenario }),
  setSeed: (seed) => set({ seed }),
  setAmiPenetration: (amiPenetration) => set({ amiPenetration }),
  setDevicePenetration: (devicePenetration) => set({ devicePenetration }),
  setEvPenetration: (evPenetration) => set({ evPenetration }),
  setSpeed: (speed) => set({ speed }),
  setIsPlaying: (isPlaying) => set({ isPlaying }),
  setCurrentTickIndex: (currentTickIndex) => set({ currentTickIndex }),
  setOfflineMode: (offlineMode) => set({ offlineMode }),

  loadOfflineFixture: async (scen: string, sd: number) => {
    set({ busy: true, error: null, status: "loading offline recording" });
    try {
      const res = await fetch(`/recorded/${scen}-${sd}.json`);
      if (!res.ok) {
        const fallbackRes = await fetch(`/recorded/heatwave-42.json`);
        if (!fallbackRes.ok) throw new Error("Offline recording fixture unavailable");
        const data = await fallbackRes.json();
        set({ ticks: data.ticks, summary: data.summary, status: "ready", currentTickIndex: 0, isPlaying: true });
      } else {
        const data = await res.json();
        set({ ticks: data.ticks, summary: data.summary, status: "ready", currentTickIndex: 0, isPlaying: true });
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Offline loading failed";
      set({ error: msg, status: "failed" });
    } finally {
      set({ busy: false });
    }
  },

  startSimulation: async () => {
    const { offlineMode, scenario, seed, amiPenetration, devicePenetration, evPenetration, speed, loadOfflineFixture } = get();

    if (offlineMode) {
      await loadOfflineFixture(scenario, seed);
      return;
    }

    set({ busy: true, error: null, status: "submitting run", isPlaying: false, ticks: [], summary: null });

    try {
      const runData = await createRun({
        scenario,
        seed,
        ticks: 96,
        carry_debt: false,
        params: {
          ami_penetration: amiPenetration,
          connected_device_penetration: devicePenetration,
          ev_penetration: evPenetration,
        },
      });

      const runId = runData.run_id;
      set({ runId });

      // Poll until ready
      for (let i = 0; i < 240; i++) {
        const statusRes = await getRunStatus(runId);
        set({ status: statusRes.status });
        if (statusRes.status === "ready") break;
        if (statusRes.status === "failed") throw new Error(statusRes.error || "Simulation failed");
        await new Promise((r) => setTimeout(r, 300));
      }

      // Fetch summary
      const sumData = await getRunSummary(runId);
      set({ summary: sumData });

      // Connect WebSocket
      if (activeWs) activeWs.close();
      const loadedTicks: TickMessage[] = [];
      activeWs = connectSimulationWebSocket(
        runId,
        speed,
        (tickMsg) => {
          loadedTicks.push(tickMsg);
          set({ ticks: [...loadedTicks] });
        },
        () => {
          set({ isPlaying: true, currentTickIndex: 0 });
        },
        () => {
          set({ offlineMode: true });
          loadOfflineFixture(scenario, seed);
        }
      );
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Simulation execution failed";
      set({ offlineMode: true, error: msg });
      await loadOfflineFixture(scenario, seed);
    } finally {
      set({ busy: false });
    }
  },

  injectTrigger: async (type: string, magnitude = 1.0) => {
    const { runId, currentTickIndex, startSimulation, offlineMode } = get();
    if (offlineMode || !runId) {
      alert(`Trigger '${type}' requires an active backend server.`);
      return;
    }

    try {
      set({ busy: true });
      await injectDisruption(runId, type, magnitude, currentTickIndex);
      await startSimulation();
    } catch {
      alert("Injection failed");
    } finally {
      set({ busy: false });
    }
  },
}));
