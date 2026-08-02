"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import { AppHeader, type AppView } from "./components/app-header";
import { AssuranceLab } from "./components/assurance-lab";
import { CommandCenter } from "./components/command-center";
import { LandingPage } from "./components/landing-page";
import { ReplayDashboard } from "./components/replay-dashboard";
import { SimulationLab } from "./components/simulation-lab";
import { StoryMode } from "./components/story-mode";
import { DEFAULT_PREFERENCES, readPreferences } from "./lib/preferences";
import { API_URL, api } from "./lib/replay";
import type { Recording, ScenarioName } from "./types";

type Surface = "landing" | "console";
type ReplayMode = "story" | "explore";

export default function Home() {
  const [surface, setSurface] = useState<Surface>("landing");
  const [view, setView] = useState<AppView>("overview");
  const [replayMode, setReplayMode] = useState<ReplayMode>("explore");
  const [scenario, setScenario] = useState<ScenarioName>(DEFAULT_PREFERENCES.scenario);
  const [recording, setRecording] = useState<Recording | null>(null);
  const [generatedRun, setGeneratedRun] = useState<{ recording: Recording; runId: string } | null>(null);
  const [online, setOnline] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loadAttempt, setLoadAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    api<{ status: string }>("/api/health")
      .then((health) => active && setOnline(health.status === "ok"))
      .catch(() => active && setOnline(false));
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    async function loadRecording() {
      try {
        const value = await api<Recording>(`/api/recordings/${scenario}?seed=42`);
        if (active) setRecording(value);
      } catch {
        try {
          const response = await fetch(`/recorded/${scenario}-42.json`);
          if (!response.ok) throw new Error("Recording not found");
          const value = await response.json() as Recording;
          if (active) setRecording(value);
        } catch (caught) {
          if (!active) return;
          setRecording(null);
          setError(caught instanceof Error ? caught.message : "Could not load the recorded replay");
        }
      } finally {
        if (active) setLoading(false);
      }
    }
    void loadRecording();
    return () => { active = false; };
  }, [scenario, loadAttempt]);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      setScenario(readPreferences().scenario);
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "auto" });
  }, [surface, view, replayMode]);

  function changeScenario(value: ScenarioName) {
    setLoading(true);
    setError(null);
    setGeneratedRun(null);
    setScenario(value);
    setReplayMode(value === "heatwave" ? "story" : "explore");
  }

  function retryRecording() {
    setError(null);
    setLoading(true);
    setLoadAttempt((attempt) => attempt + 1);
  }

  function enterConsole(nextView: AppView = "overview") {
    setView(nextView);
    setSurface("console");
    window.scrollTo({ top: 0 });
  }

  function watchStory() {
    setGeneratedRun(null);
    setScenario("heatwave");
    setReplayMode("story");
    enterConsole("replay");
  }

  function openGeneratedRun(nextRecording: Recording, runId: string) {
    setGeneratedRun({ recording: nextRecording, runId });
    setScenario(nextRecording.meta.scenario);
    setReplayMode("explore");
    setView("overview");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  const activeRecording = generatedRun?.recording ?? recording;

  return <AnimatePresence mode="wait">
    {surface === "landing" ? <LandingPage key="landing" recording={recording} online={online} onEnter={() => enterConsole("overview")} onWatch={watchStory} /> :
      <motion.div key="console" className="console-shell" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: .28 }}>
        <AppHeader view={view} onView={setView} scenario={scenario} onScenario={changeScenario} online={online} onExit={() => setSurface("landing")} />
        <div className="console-content">
          <AnimatePresence mode="wait">
            <motion.div
              key={loading ? `loading-${scenario}` : `${view}-${view === "replay" ? replayMode : "main"}`}
              className="console-view"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -5 }}
              transition={{ duration: .2, ease: "easeOut" }}
            >
              {loading && <main className="loading-screen"><div className="loading-grid" aria-hidden="true">{Array.from({ length: 60 }, (_, index) => <i key={index} />)}</div><div><span>Loading recorded network</span><strong>{scenario.replaceAll("_", " ")}</strong><p>96 intervals · 60 transformers · two control strategies</p></div></main>}
              {!loading && error && <main className="error-screen"><span>Replay unavailable</span><h1>The recorded scenario could not be loaded.</h1><p>{error}</p><p>Confirm the backend is running at <code>{API_URL}</code>.</p><button className="primary-action" onClick={retryRecording}>Try again</button></main>}
              {!loading && activeRecording && view === "overview" && <CommandCenter key={`${scenario}-${generatedRun?.runId ?? "demo"}-overview`} recording={activeRecording} scenario={scenario} online={online} source={generatedRun ? { kind: "generated", runId: generatedRun.runId } : { kind: "demo" }} onOpenReplay={() => { setReplayMode("explore"); setView("replay"); }} onOpenSimulation={() => setView("simulate")} />}
              {!loading && activeRecording && view === "replay" && replayMode === "story" && <StoryMode recording={activeRecording} onExplore={() => setReplayMode("explore")} />}
              {!loading && activeRecording && view === "replay" && replayMode === "explore" && <ReplayDashboard recording={activeRecording} onStory={scenario === "heatwave" ? () => setReplayMode("story") : undefined} />}
              {view === "simulate" && <SimulationLab online={online} onOpenCommandCenter={openGeneratedRun} />}
              {view === "assurance" && <AssuranceLab online={online} />}
            </motion.div>
          </AnimatePresence>
        </div>
      </motion.div>}
  </AnimatePresence>;
}
