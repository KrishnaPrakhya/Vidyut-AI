"use client";

import Link from "next/link";
import { useState } from "react";

type AccountPage = "profile" | "settings";

type AccountConsoleProps = {
  page: AccountPage;
};

function AccountFrame({ page, children }: AccountConsoleProps & { children: React.ReactNode }) {
  return <main className="account-console">
    <aside className="account-sidebar">
      <Link className="account-brand" href="/" aria-label="Return to Vidyut landing page"><span>V</span><strong>VIDYUT</strong><small>Command</small></Link>
      <nav aria-label="Account navigation">
        <span className="account-nav-label">OPERATOR</span>
        <Link className={page === "profile" ? "active" : ""} href="/profile"><i>◉</i><span>Profile</span></Link>
        <Link className={page === "settings" ? "active" : ""} href="/settings"><i>⚙</i><span>Settings</span></Link>
      </nav>
      <div className="account-sidebar-foot"><i /><span><strong>Secure session</strong><small>Audit logging enabled</small></span></div>
    </aside>
    <section className="account-stage">
      <header className="account-topbar">
        <div className="account-crumb"><span>VIDYUT / OPERATOR</span><b>/</b><strong>{page === "profile" ? "Profile" : "Settings"}</strong></div>
        <Link className="account-return" href="/">← Command center</Link>
      </header>
      <div className="account-content">{children}</div>
    </section>
  </main>;
}

export function ProfileConsole() {
  const [saved, setSaved] = useState(false);

  return <AccountFrame page="profile">
    <div className="account-heading">
      <div><p className="account-kicker">Identity record / OP-041</p><h1>Operator profile</h1><p>Control-room identity, assignment and access record.</p></div>
      <span className="verified-mark">✓ Verified operator</span>
    </div>
    <div className="profile-layout">
      <section className="identity-card account-panel">
        <div className="profile-monogram">OP</div>
        <div><p className="account-kicker">Primary operator</p><h2>Operator</h2><span>Distribution response desk</span></div>
        <dl>
          <div><dt>Clearance</dt><dd><i className="clearance-dot" />Level 3 / Control</dd></div>
          <div><dt>Shift</dt><dd>06:00 — 14:00 IST</dd></div>
          <div><dt>Base zone</dt><dd>South distribution</dd></div>
        </dl>
      </section>
      <section className="account-panel account-form-panel">
        <div className="panel-title"><div><p className="account-kicker">Editable details</p><h2>Profile information</h2></div><span>All changes logged</span></div>
        <form onSubmit={(event) => { event.preventDefault(); setSaved(true); }}>
          <label>Display name<input defaultValue="Operator" /></label>
          <label>Work email<input type="email" defaultValue="operator@vidyut.grid" /></label>
          <label>Response region<select defaultValue="south"><option value="south">South distribution</option><option value="central">Central distribution</option><option value="north">North distribution</option></select></label>
          <div className="form-actions"><button type="submit">{saved ? "Saved to operator record" : "Save changes"}</button>{saved && <span role="status">✓ Changes recorded</span>}</div>
        </form>
      </section>
    </div>
    <section className="access-section"><div className="panel-title"><div><p className="account-kicker">Authorizations</p><h2>Current access</h2></div><span>Reviewed 18 Jul 2026</span></div><div className="access-grid">
      {[['Command center', 'View live network state', 'Active'], ['Simulation lab', 'Create and compare runs', 'Active'], ['Assurance reports', 'Read evidence and model outputs', 'Active']].map(([title, description, status]) => <article key={title}><i>↗</i><div><strong>{title}</strong><p>{description}</p></div><span>{status}</span></article>)}
    </div></section>
  </AccountFrame>;
}

export function SettingsConsole() {
  const [saved, setSaved] = useState(false);
  const [alerts, setAlerts] = useState(true);
  const [digest, setDigest] = useState(true);
  const [compact, setCompact] = useState(false);
  const rows = [
    ["Critical response alerts", "Surface a signal when a feeder enters critical response.", alerts, setAlerts],
    ["Shift digest", "Send a concise close-of-shift summary to your work email.", digest, setDigest],
    ["Compact telemetry", "Reduce visual density in command-center data panels.", compact, setCompact],
  ] as const;

  return <AccountFrame page="settings">
    <div className="account-heading"><div><p className="account-kicker">Workspace preferences</p><h1>System settings</h1><p>Choose how the command environment notifies and supports you.</p></div><span className="settings-version">Console v1.0 / Stable</span></div>
    <div className="settings-layout">
      <section className="account-panel preferences-panel"><div className="panel-title"><div><p className="account-kicker">Signal control</p><h2>Notifications</h2></div><span>Personal only</span></div>
        {rows.map(([title, description, checked, setChecked]) => <label className="setting-row" key={title}><span><strong>{title}</strong><small>{description}</small></span><input type="checkbox" checked={checked} onChange={(event) => setChecked(event.target.checked)} /><i aria-hidden="true" /></label>)}
      </section>
      <section className="account-panel security-panel"><div className="panel-title"><div><p className="account-kicker">Access protection</p><h2>Session security</h2></div><span className="security-state">Protected</span></div>
        <div className="security-item"><i>✓</i><div><strong>Multi-factor authentication</strong><small>Authenticator app confirmed</small></div><button type="button">Manage</button></div>
        <div className="security-item"><i>✓</i><div><strong>Trusted device</strong><small>Current session verified</small></div><button type="button">Review</button></div>
        <div className="security-note"><i>●</i> Identity and preference changes are appended to the operator audit record.</div>
      </section>
    </div>
    <section className="account-panel defaults-panel"><div><p className="account-kicker">Operating defaults</p><h2>Command-center display</h2><p>These defaults apply when opening a new operational session.</p></div><div className="defaults-controls"><label>Default scenario<select defaultValue="heatwave"><option value="heatwave">Heatwave</option><option value="normal">Normal day</option><option value="ev">EV surge</option></select></label><button type="button" onClick={() => setSaved(true)}>{saved ? "Preferences saved" : "Save preferences"}</button></div></section>
  </AccountFrame>;
}
