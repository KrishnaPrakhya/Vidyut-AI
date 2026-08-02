"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { API_URL, api } from "../lib/replay";
import { DEFAULT_PREFERENCES, REPLAY_SPEEDS, clearPreferences, readPreferences, storedPreferences, writePreferences, type Preferences } from "../lib/preferences";

type AccountPage = "profile" | "settings";

type Health = {
  status: string;
  scenarios: string[];
  database: { status: string; configured: boolean; reachable: boolean; host: string | null; error: string | null };
  automation: { n8n_webhook_configured: boolean; callback_auth_configured: boolean; public_api_url_configured: boolean };
};

function useHealth() {
  const [health, setHealth] = useState<Health | null>(null);
  const [state, setState] = useState<"loading" | "online" | "offline">("loading");

  useEffect(() => {
    let active = true;
    api<Health>("/api/health")
      .then((value) => { if (!active) return; setHealth(value); setState(value.status === "ok" ? "online" : "offline"); })
      .catch(() => { if (active) setState("offline"); });
    return () => { active = false; };
  }, []);

  return { health, state };
}

function AccountFrame({ page, state, children }: { page: AccountPage; state: "loading" | "online" | "offline"; children: React.ReactNode }) {
  return <main className="account-console">
    <aside className="account-sidebar">
      <Link className="account-brand" href="/" aria-label="Return to Vidyut landing page"><span>V</span><strong>VIDYUT</strong><small>Command</small></Link>
      <nav aria-label="Console navigation">
        <span className="account-nav-label">CONSOLE</span>
        <Link className={page === "profile" ? "active" : ""} href="/profile"><i>◉</i><span>Session</span></Link>
        <Link className={page === "settings" ? "active" : ""} href="/settings"><i>⚙</i><span>Preferences</span></Link>
      </nav>
      <div className={`account-sidebar-foot ${state}`}><i /><span><strong>{state === "online" ? "Simulation core connected" : state === "loading" ? "Checking backend" : "Recorded replay only"}</strong><small>{API_URL.replace(/^https?:\/\//, "")}</small></span></div>
    </aside>
    <section className="account-stage">
      <header className="account-topbar">
        <div className="account-crumb"><span>VIDYUT / CONSOLE</span><b>/</b><strong>{page === "profile" ? "Session" : "Preferences"}</strong></div>
        <Link className="account-return" href="/">← Command center</Link>
      </header>
      <div className="account-content">{children}</div>
    </section>
  </main>;
}

export function ProfileConsole() {
  const { health, state } = useHealth();
  const database = health?.database;
  const automation = health?.automation;

  const capabilities: [string, string, boolean | undefined][] = [
    ["Operator digest webhook", "N8N_WEBHOOK_URL and N8N_WEBHOOK_TOKEN are both set, so a run can hand its notification outbox to the automation workflow.", automation?.n8n_webhook_configured],
    ["Delivery callback auth", "N8N_CALLBACK_TOKEN is set, so the workflow can report back whether the digest actually reached its recipient.", automation?.callback_auth_configured],
    ["Public API address", "VIDYUT_PUBLIC_API_URL is set, so the audit-report link inside a dispatched digest resolves from outside this machine.", automation?.public_api_url_configured],
  ];

  return <AccountFrame page="profile" state={state}>
    <div className="account-heading">
      <div><p className="account-kicker">Console session</p><h1>Session and environment</h1><p>What this browser is connected to, and what the deployment behind it can currently do. Every value on this page is read from <code>/api/health</code>.</p></div>
      <span className={`verified-mark ${state !== "online" ? "muted" : ""}`}>{state === "online" ? "✓ Backend reachable" : state === "loading" ? "· Checking" : "✕ Backend unreachable"}</span>
    </div>
    <div className="profile-layout">
      <section className="identity-card account-panel">
        <div className="profile-monogram">{state === "online" ? "◉" : "○"}</div>
        <div><p className="account-kicker">Runtime</p><h2>{state === "online" ? "Simulation core" : "Offline"}</h2><span>{API_URL}</span></div>
        <dl>
          <div><dt>Authentication</dt><dd>Not configured</dd></div>
          <div><dt>Scenarios</dt><dd>{health ? health.scenarios.map((name) => name.replaceAll("_", " ")).join(", ") : "—"}</dd></div>
          <div><dt>Persistence</dt><dd>{database ? database.configured ? database.reachable ? `Postgres · ${database.host ?? "connected"}` : "Configured, unreachable" : "In-memory (no DATABASE_URL)" : "—"}</dd></div>
          <div><dt>Run history</dt><dd>{database?.reachable ? "Retained across restarts" : "Lost when the API restarts"}</dd></div>
        </dl>
      </section>
      <section className="account-panel account-form-panel">
        <div className="panel-title"><div><p className="account-kicker">Access model</p><h2>There is no account system</h2></div><span>By design</span></div>
        <div className="account-prose">
          <p>Vidyut has no sign-in, no user records and no roles. Anyone who opens this URL sees exactly the same console with exactly the same permissions. There is nothing here to personalise because there is no person to attach it to.</p>
          <p>Nothing you type into this console is stored on a server. The one address the application ever accepts — the operator digest recipient in the Simulation Lab — is used for a single delivery and is not retained afterwards.</p>
          <p>A real deployment would need head-end and SCADA integration, IS 15959 / IEC 62351 security work and regulatory approval before any of this touched a live network. Authentication would arrive with that work, not before it.</p>
        </div>
      </section>
    </div>
    <section className="access-section">
      <div className="panel-title"><div><p className="account-kicker">Automation readiness</p><h2>Outbound integration</h2></div><span>From environment variables</span></div>
      <div className="access-grid">
        {capabilities.map(([title, description, ready]) => <article key={title} className={ready ? "" : "inactive"}><i>{ready ? "✓" : "–"}</i><div><strong>{title}</strong><p>{description}</p></div><span>{ready === undefined ? "Unknown" : ready ? "Configured" : "Not configured"}</span></article>)}
      </div>
    </section>
  </AccountFrame>;
}

export function SettingsConsole() {
  const { state } = useHealth();
  const [preferences, setPreferences] = useState<Preferences>(DEFAULT_PREFERENCES);
  const [stored, setStored] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setPreferences(readPreferences());
    setStored(storedPreferences());
  }, []);

  function update(patch: Partial<Preferences>) {
    setPreferences((current) => ({ ...current, ...patch }));
    setSaved(false);
  }

  function save() {
    writePreferences(preferences);
    setStored(storedPreferences());
    setSaved(true);
  }

  function reset() {
    clearPreferences();
    setPreferences(DEFAULT_PREFERENCES);
    setStored(null);
    setSaved(false);
  }

  return <AccountFrame page="settings" state={state}>
    <div className="account-heading">
      <div><p className="account-kicker">Browser preferences</p><h1>Console preferences</h1><p>Two settings that change how the command center opens. Both are stored in this browser only and are read back by the console on load.</p></div>
      <span className={`settings-version ${stored ? "" : "muted"}`}>{stored ? "Stored in this browser" : "Using defaults"}</span>
    </div>
    <div className="settings-layout">
      <section className="account-panel account-form-panel">
        <div className="panel-title"><div><p className="account-kicker">Startup defaults</p><h2>Opening state</h2></div><span>Applied on next load</span></div>
        <form onSubmit={(event) => { event.preventDefault(); save(); }}>
          <label>Default scenario
            <select value={preferences.scenario} onChange={(event) => update({ scenario: event.target.value as Preferences["scenario"] })}>
              <option value="normal">Normal day</option>
              <option value="heatwave">Heatwave</option>
              <option value="ev_surge">EV surge</option>
            </select>
          </label>
          <label>Replay speed
            <select value={preferences.replayMs} onChange={(event) => update({ replayMs: Number(event.target.value) })}>
              {REPLAY_SPEEDS.map((speed) => <option key={speed.ms} value={speed.ms}>{speed.label}</option>)}
            </select>
          </label>
          <div className="form-actions"><button type="submit">{saved ? "Preferences saved" : "Save preferences"}</button>{saved && <span role="status">✓ Written to this browser</span>}</div>
        </form>
      </section>
      <section className="account-panel security-panel">
        <div className="panel-title"><div><p className="account-kicker">What is stored</p><h2>Local storage</h2></div><span>This browser only</span></div>
        <div className="security-item"><i>{stored ? "●" : "–"}</i><div><strong>vidyut.preferences</strong><small className="storage-value">{stored ?? "Nothing written yet"}</small></div><button type="button" onClick={reset} disabled={!stored}>Clear</button></div>
        <div className="security-note"><i>●</i> This is the complete list. Vidyut sets no cookies, stores no identity and sends no preference to the API. Clearing it returns the console to a {DEFAULT_PREFERENCES.scenario.replaceAll("_", " ")} scenario at standard speed.</div>
      </section>
    </div>
  </AccountFrame>;
}
