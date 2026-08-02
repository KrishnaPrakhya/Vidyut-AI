"use client";

import { useState } from "react";
import Link from "next/link";
import type { ScenarioName } from "../types";

export type AppView = "overview" | "replay" | "simulate" | "assurance";

type Props = {
  view: AppView;
  onView: (view: AppView) => void;
  scenario: ScenarioName;
  onScenario: (scenario: ScenarioName) => void;
  online: boolean;
  onExit: () => void;
};

const items: Array<[AppView, string, string]> = [
  ["overview", "⌘", "Command overview"],
  ["replay", "◫", "Digital twin replay"],
  ["simulate", "△", "Simulation lab"],
  ["assurance", "◇", "Assurance & models"],
];

export function AppHeader({ view, onView, scenario, onScenario, online, onExit }: Props) {
  const [jump, setJump] = useState("");

  function jumpToSection() {
    const query = jump.trim().toLowerCase();
    if (!query) return;
    const match = items.find(([id, , label]) => id.includes(query) || label.toLowerCase().includes(query));
    if (!match) return;
    onView(match[0]);
    setJump("");
  }

  return <>
    <aside className="console-sidebar">
      <button className="console-brand" type="button" onClick={onExit} aria-label="Return to Vidyut landing page"><span>V</span><strong>VIDYUT</strong><small>Command</small></button>
      <nav aria-label="Command center sections">
        <span className="nav-label">OPERATIONS</span>
        {items.map(([id, glyph, label]) => <button type="button" key={id} className={view === id ? "active" : ""} onClick={() => onView(id)}><i>{glyph}</i><span>{label}</span>{view === id && <b />}</button>)}
      </nav>
      <div className="sidebar-foot">
        <div className={`sidebar-health ${online ? "online" : ""}`}><i /><span><strong>{online ? "Simulation core online" : "Recorded mode"}</strong><small>{online ? "API responding" : "Backend unavailable"}</small></span></div>
        <button type="button" onClick={onExit}>← Back to site</button>
      </div>
    </aside>

    <header className="console-topbar">
      <div className="console-breadcrumb"><span>VIDYUT / COMMAND</span><b>/</b><strong>{items.find(([id]) => id === view)?.[2]}</strong></div>
      <form className="console-search" onSubmit={(event) => { event.preventDefault(); jumpToSection(); }}>
        <span>⌕</span>
        <input list="command-destinations" value={jump} onChange={(event) => setJump(event.target.value)} aria-label="Jump to command center section" placeholder="Jump to replay, simulation or assurance…" />
        <datalist id="command-destinations">{items.map(([, , label]) => <option value={label} key={label} />)}</datalist>
      </form>
      <label className="console-scenario"><span>Scenario</span><select value={scenario} onChange={(event) => onScenario(event.target.value as ScenarioName)}><option value="normal">Normal day</option><option value="heatwave">Heatwave</option><option value="ev_surge">EV surge</option></select></label>
      <Link className="operator-badge" href="/profile" aria-label="Open session and environment"><span>◉</span><p><strong>Session</strong><small>{online ? "Core connected" : "Recorded replay"}</small></p></Link>
    </header>

    <nav className="mobile-console-nav" aria-label="Mobile command sections">{items.map(([id, glyph, label]) => <button type="button" key={id} className={view === id ? "active" : ""} onClick={() => onView(id)}><i>{glyph}</i><span>{label.split(" ")[0]}</span></button>)}</nav>
  </>;
}
