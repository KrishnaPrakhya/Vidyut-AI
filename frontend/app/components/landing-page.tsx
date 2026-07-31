"use client";

import dynamic from "next/dynamic";
import { motion, useReducedMotion, useScroll, useTransform } from "framer-motion";
import { useMemo, useState } from "react";
import type { Recording } from "../types";
import { formatNumber } from "../lib/replay";

const Network3D = dynamic(
  () => import("./network-3d").then((module) => module.Network3D),
  { ssr: false, loading: () => <div className="twin-loading"><i /><span>Starting digital twin</span></div> },
);

type LandingPageProps = {
  recording: Recording | null;
  online: boolean;
  onEnter: () => void;
  onWatch: () => void;
};

const loop = [
  ["01", "Sense", "Read demand and equipment state every 15 minutes."],
  ["02", "Forecast", "Look one hour ahead at each transformer, not just the whole feeder."],
  ["03", "Decide", "Use the smallest fair intervention that can remove the risk."],
  ["04", "Respond", "Shift flexible demand, then limit locally only when needed."],
  ["05", "Verify", "Measure the result and carry the household burden ledger forward."],
];

function Neighborhood({ dark, label }: { dark: number; label: string }) {
  const total = 35;
  const darkCount = Math.min(total, Math.ceil((dark / 70) * total));
  return <div className="landing-neighborhood" aria-label={`${label}: ${dark} homes dark`}>
    <div className="neighborhood-sky"><span>{label}</span><i /></div>
    <div className="neighborhood-homes">{Array.from({ length: total }, (_, index) => <i className={index < darkCount ? "dark" : "lit"} key={index} />)}</div>
    <strong>{dark}</strong><small>homes without power</small>
  </div>;
}

export function LandingPage({ recording, online, onEnter, onWatch }: LandingPageProps) {
  const reduced = useReducedMotion();
  const { scrollYProgress } = useScroll();
  const progress = useTransform(scrollYProgress, [0, 1], ["0%", "100%"]);
  const [selectedDt, setSelectedDt] = useState("F1-DT17");
  const focusTick = recording?.ticks[67] ?? recording?.ticks[0];
  const baselineDt = focusTick?.arms.baseline.dts.find((dt) => dt.id === selectedDt);
  const vidyutDt = focusTick?.arms.vidyut.dts.find((dt) => dt.id === selectedDt);
  const overloadDt = useMemo(() => recording ? [...recording.ticks]
    .slice(0, (focusTick?.t ?? recording.ticks.length - 1) + 1)
    .reverse()
    .map((frame) => frame.arms.baseline.dts.find((dt) => dt.id === selectedDt))
    .find((dt) => (dt?.loading_pct ?? 0) >= 100) : undefined, [focusTick?.t, recording, selectedDt]);
  const totals = recording?.summary.arms;
  const prevented = totals
    ? Math.round(100 * (1 - totals.vidyut.homes_dark_minutes / totals.baseline.homes_dark_minutes))
    : 96;
  const activeTargets = useMemo(
    () => new Set(focusTick?.arms.vidyut.events.map((event) => event.target) ?? []),
    [focusTick],
  );

  return <motion.main className="landing" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
    <motion.div className="scroll-progress" style={{ width: progress }} />
    <header className="landing-nav">
      <button className="landing-brand" type="button" onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}>
        <span>V</span><strong>VIDYUT</strong><small>Grid operating intelligence</small>
      </button>
      <nav aria-label="Landing sections">
        <a href="#problem">The problem</a>
        <a href="#response">How it responds</a>
        <a href="#platform">Platform</a>
      </nav>
      <button className="nav-launch" type="button" onClick={onEnter}>Open command center <span>↗</span></button>
    </header>

    <section className="landing-hero">
      <motion.div className="hero-copy" initial={{ opacity: 0, y: reduced ? 0 : 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .7 }}>
        <div className="system-line"><i className={online ? "online" : ""} /><span>System status</span><strong>{online ? "Connected to simulation core" : "Recorded demo available"}</strong></div>
        <h1>Keep the lights on<br /><em>before</em> the grid breaks.</h1>
        <p>Vidyut sees transformer stress before it becomes a blackout, coordinates flexible demand, and protects essential services without switching off an entire locality.</p>
        <div className="hero-actions">
          <button className="hero-primary" type="button" onClick={onWatch}>Watch the heatwave response <span>▶</span></button>
          <button className="hero-secondary" type="button" onClick={onEnter}>Explore the live console <span>→</span></button>
        </div>
        <div className="hero-proof"><span><b>96</b> intervals replayed</span><span><b>60</b> transformers observed</span><span><b>2</b> strategies compared</span></div>
      </motion.div>

      <motion.div className="hero-twin" initial={{ opacity: 0, scale: reduced ? 1 : .96 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: .8, delay: .15 }}>
        <div className="hero-twin-head"><span><i />Digital twin · {focusTick?.clock ?? "16:45"}</span><strong>HEATWAVE / VIDYUT</strong></div>
        {focusTick ? <Network3D snapshot={focusTick.arms.vidyut} label="Vidyut-controlled network" selectedDt={selectedDt} onSelect={setSelectedDt} activeTargets={activeTargets} presentation /> : <div className="twin-loading"><i /><span>Loading recorded network</span></div>}
        <div className="hero-twin-stat left"><span>Selected asset</span><strong>{selectedDt}</strong><small>{formatNumber(vidyutDt?.loading_pct)}% loading</small></div>
        <div className="hero-twin-stat right"><span>Critical services</span><strong>100%</strong><small>kept powered</small></div>
      </motion.div>
    </section>

    <section className="landing-signal" aria-label="Key result">
      <span>Recorded heatwave · seed 42</span>
      <strong>{prevented}%</strong>
      <p>fewer homes-dark minutes than conventional protection</p>
      <button type="button" onClick={onWatch}>See the recorded evidence →</button>
    </section>

    <section className="problem-section" id="problem">
      <div className="section-intro">
        <span className="landing-kicker">01 / THE FAILURE MODE</span>
        <h2>A hot transformer should not mean a dark neighborhood.</h2>
        <p>Conventional protection notices the danger after the limit is crossed. Its safest available response can be the bluntest one: disconnect every home behind that transformer.</p>
      </div>
      <div className="failure-sequence">
        <article><span>16:15</span><i className="heat-symbol">☀</i><strong>Heatwave demand rises</strong><p>Cooling demand pushes one locality toward its equipment limit.</p></article>
        <b>→</b>
        <article className="danger"><span>16:30</span><i>!</i><strong>{formatNumber(overloadDt?.loading_pct ?? 103.1)}% loaded</strong><p>The transformer is already beyond its rated capacity.</p></article>
        <b>→</b>
        <article className="blackout"><span>16:45</span><i>×</i><strong>Transformer disconnected</strong><p>Protection saves the equipment by taking the whole locality offline.</p></article>
      </div>
    </section>

    <section className="blackout-comparison">
      <div className="comparison-copy"><span className="landing-kicker">SAME DEMAND · DIFFERENT CONTROL</span><h2>One event. Two outcomes.</h2><p>At the same recorded moment, conventional protection has disconnected the locality. Vidyut acted earlier and keeps it energised.</p></div>
      <div className="neighborhood-compare">
        <Neighborhood dark={baselineDt?.households_dark ?? 70} label="BASELINE" />
        <div className="comparison-vs"><span>same</span><b>VS</b><span>demand</span></div>
        <Neighborhood dark={vidyutDt?.households_dark ?? 0} label="VIDYUT" />
      </div>
      <div className="protected-service"><i>+</i><span><small>Critical service on this network</small><strong>Hospital remains powered</strong></span><b>PROTECTED</b></div>
    </section>

    <section className="response-section" id="response">
      <div className="section-intro split"><div><span className="landing-kicker">02 / AUTONOMOUS RESPONSE</span><h2>Intervene early.<br />Escalate carefully.</h2></div><p>Vidyut does not jump from forecast to disconnection. It follows an ordered response ladder, records who was affected, and verifies whether the action worked.</p></div>
      <div className="response-loop">
        {loop.map(([number, title, body], index) => <motion.article key={title} initial={{ opacity: 0, y: reduced ? 0 : 18 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, amount: .4 }} transition={{ delay: index * .08 }}><span>{number}</span><div className="loop-icon"><i /></div><strong>{title}</strong><p>{body}</p></motion.article>)}
      </div>
      <div className="response-evidence">
        <div><span>Forecast before outage</span><strong>~60 min</strong><small>transformer-level horizon</small></div>
        <div><span>Vidyut loading at event</span><strong>{formatNumber(vidyutDt?.loading_pct ?? 89.7)}%</strong><small>transformer remains energised</small></div>
        <div><span>Homes dark at locality</span><strong>{vidyutDt?.households_dark ?? 0}</strong><small>versus {baselineDt?.households_dark ?? 70} baseline</small></div>
      </div>
    </section>

    <section className="platform-section" id="platform">
      <div className="section-intro split"><div><span className="landing-kicker">03 / ONE OPERATING PICTURE</span><h2>From story to evidence<br />without changing tools.</h2></div><p>The same recorded frames power the presentation, interactive replay and operator console. Fresh scenarios use the live simulation API, not a visual mock.</p></div>
      <div className="platform-preview">
        <div className="preview-sidebar"><b>V</b>{["Overview", "Digital twin", "Replay", "Simulation", "Assurance"].map((item, index) => <span className={index === 0 ? "active" : ""} key={item}><i />{item}</span>)}</div>
        <div className="preview-main">
          <div className="preview-top"><span>COMMAND / HEATWAVE-42</span><i /><strong>GRID STABLE</strong></div>
          <div className="preview-kpis"><span><small>Network health</small><strong>98.4%</strong></span><span><small>Forecast confidence</small><strong>94.2%</strong></span><span><small>Homes protected</small><strong>{formatNumber((totals?.baseline.homes_dark_minutes ?? 0) - (totals?.vidyut.homes_dark_minutes ?? 0), 0)}</strong></span><span><small>Critical uptime</small><strong>100%</strong></span></div>
          <div className="preview-grid"><div className="preview-chart"><span>Demand forecast</span>{Array.from({ length: 34 }, (_, index) => <i key={index} style={{ height: `${22 + Math.sin(index / 5) * 12 + index * 1.2}%` }} />)}</div><div className="preview-map"><span>Network topology</span>{Array.from({ length: 60 }, (_, index) => <i key={index} className={index === 16 ? "hot" : index % 9 === 0 ? "active" : ""} />)}</div><div className="preview-feed"><span>Decision feed</span><p><b>Forecast</b> F1-DT17 risk detected</p><p><b>Action</b> Flexible load reduced</p><p><b>Result</b> Locality stays powered</p></div></div>
        </div>
      </div>
      <div className="platform-modules">
        <button type="button" onClick={onEnter}><span>01</span><strong>Command center</strong><p>See network state, forecast risk, decisions and outcomes in one synchronized view.</p><b>Open overview →</b></button>
        <button type="button" onClick={onWatch}><span>02</span><strong>Recorded replay</strong><p>Scrub through all 96 intervals and compare the same transformer under both strategies.</p><b>Watch replay →</b></button>
        <button type="button" onClick={onEnter}><span>03</span><strong>Scenario lab</strong><p>Change penetration, peak and duration, then run the real simulation backend.</p><b>Run scenario →</b></button>
        <button type="button" onClick={onEnter}><span>04</span><strong>Measurement assurance</strong><p>Keep registered, estimated and verified flexibility visibly separate.</p><b>Inspect evidence →</b></button>
      </div>
    </section>

    <section className="landing-outcome">
      <span className="landing-kicker">RECORDED END-OF-DAY OUTCOME</span>
      <h2>Reliability that can be inspected,<br />not merely claimed.</h2>
      <div className="outcome-numbers">
        <div><small>Homes-dark minutes</small><strong>{formatNumber(totals?.baseline.homes_dark_minutes, 0)}</strong><i>→</i><b>{formatNumber(totals?.vidyut.homes_dark_minutes, 0)}</b></div>
        <div><small>Unserved energy</small><strong>{formatNumber(totals?.baseline.unserved_kwh)} kWh</strong><i>→</i><b>{formatNumber(totals?.vidyut.unserved_kwh)} kWh</b></div>
        <div><small>Critical uptime</small><strong>{formatNumber(totals?.baseline.critical_uptime_pct, 2)}%</strong><i>→</i><b>{formatNumber(totals?.vidyut.critical_uptime_pct, 2)}%</b></div>
      </div>
      <p>Simulated heatwave · deterministic seed 42 · identical network and demand in both arms</p>
    </section>

    <section className="landing-cta">
      <div><span>THE GRID EVENT IS ALREADY RECORDED.</span><h2>Now watch every decision.</h2></div>
      <button type="button" onClick={onEnter}>Enter Vidyut command <span>↗</span></button>
    </section>
    <footer className="landing-footer"><div><b>VIDYUT</b><span>Distribution intelligence for a more reliable grid.</span></div><p>Recorded outputs are simulated · Evidence sources are labelled · Critical loads are protected</p></footer>
  </motion.main>;
}
