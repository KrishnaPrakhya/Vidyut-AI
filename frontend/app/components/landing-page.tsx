"use client";

import dynamic from "next/dynamic";
import Image from "next/image";
import { motion, useReducedMotion, useScroll, useTransform } from "framer-motion";
import { useEffect, useMemo, useState } from "react";
import type { ArmName, Recording } from "../types";
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

type HeroBeat = {
  id: "surge" | "blackout" | "protected";
  arm: ArmName;
  tick: number;
  label: string;
  title: string;
  body: string;
  metric: string;
  metricLabel: string;
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
  const [heroBeatIndex, setHeroBeatIndex] = useState(0);
  const focusTick = recording?.ticks[67] ?? recording?.ticks[0];
  const baselineDt = focusTick?.arms.baseline.dts.find((dt) => dt.id === selectedDt);
  const vidyutDt = focusTick?.arms.vidyut.dts.find((dt) => dt.id === selectedDt);
  const overloadDt = useMemo(() => recording ? [...recording.ticks]
    .slice(0, (focusTick?.t ?? recording.ticks.length - 1) + 1)
    .reverse()
    .map((frame) => frame.arms.baseline.dts.find((dt) => dt.id === selectedDt))
    .find((dt) => (dt?.loading_pct ?? 0) >= 100) : undefined, [focusTick?.t, recording, selectedDt]);
  // The comparison must never depend on selectedDt: a click in the hero twin would otherwise
  // silently move it to a transformer with no outage and the contrast would vanish.
  const divergence = useMemo(() => {
    if (!recording) return null;
    let best: { tick: number; clock: string; dtId: string; baselineDark: number; vidyutDark: number; vidyutLoad: number } | null = null;
    for (const frame of recording.ticks) {
      const baselineById = new Map(frame.arms.baseline.dts.map((dt) => [dt.id, dt]));
      for (const vidyutDt of frame.arms.vidyut.dts) {
        const baselineDt = baselineById.get(vidyutDt.id);
        if (!baselineDt) continue;
        const gap = baselineDt.households_dark - vidyutDt.households_dark;
        if (gap > (best ? best.baselineDark - best.vidyutDark : 0)) {
          best = {
            tick: frame.t,
            clock: frame.clock,
            dtId: vidyutDt.id,
            baselineDark: baselineDt.households_dark,
            vidyutDark: vidyutDt.households_dark,
            vidyutLoad: vidyutDt.loading_pct,
          };
        }
      }
    }
    return best;
  }, [recording]);

  const totals = recording?.summary.arms;
  const prevented = totals
    ? Math.round(100 * (1 - totals.vidyut.homes_dark_minutes / totals.baseline.homes_dark_minutes))
    : 96;
  const eventTick = divergence?.tick ?? focusTick?.t ?? 67;
  const surgeTick = Math.max(0, eventTick - 3);
  const savedHomes = Math.max(0, (divergence?.baselineDark ?? 70) - (divergence?.vidyutDark ?? 0));
  const heroBeats: HeroBeat[] = [
    {
      id: "surge",
      arm: "baseline",
      tick: surgeTick,
      label: "01 · Heatwave evening",
      title: "Everyone reaches for cooling at the same time.",
      body: "Power use rises across hundreds of homes. One neighborhood is getting dangerously close to a blackout.",
      metric: "Demand rising",
      metricLabel: "danger is building",
    },
    {
      id: "blackout",
      arm: "baseline",
      tick: eventTick,
      label: "02 · Without Vidyut",
      title: `${divergence?.baselineDark ?? 70} homes suddenly go dark.`,
      body: "Standard safety protection prevents equipment damage by switching off the entire neighborhood.",
      metric: `${divergence?.baselineDark ?? 70} homes`,
      metricLabel: "without power",
    },
    {
      id: "protected",
      arm: "vidyut",
      tick: eventTick,
      label: "03 · With Vidyut",
      title: `${savedHomes || 70} homes stay powered.`,
      body: "Vidyut sees the danger early and briefly adjusts flexible electricity use. Homes stay lit and critical medical loads keep running.",
      metric: "Critical loads on",
      metricLabel: "essential care protected",
    },
  ];
  const activeHeroBeat = heroBeats[heroBeatIndex] ?? heroBeats[0];
  const heroFrame = recording?.ticks[Math.min(activeHeroBeat.tick, Math.max(0, recording.ticks.length - 1))] ?? focusTick;
  const heroSnapshot = heroFrame?.arms[activeHeroBeat.arm];
  const heroSelectedDt = divergence?.dtId ?? selectedDt;
  const heroActiveTargets = useMemo(
    () => new Set(activeHeroBeat.arm === "vidyut" ? heroFrame?.arms.vidyut.events.map((event) => event.target) ?? [] : []),
    [activeHeroBeat.arm, heroFrame],
  );

  useEffect(() => {
    if (reduced || !recording) return;
    const timer = window.setTimeout(() => setHeroBeatIndex((current) => (current + 1) % heroBeats.length), 4400);
    return () => window.clearTimeout(timer);
  }, [heroBeatIndex, recording, reduced, heroBeats.length]);

  return <motion.main className="landing" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
    <motion.div className="scroll-progress" style={{ width: progress }} />
    <header className="landing-nav">
      <button className="landing-brand" type="button" onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}>
        <span>V</span><strong>VIDYUT</strong><small>Neighborhood power protection</small>
      </button>
      <nav aria-label="Landing sections">
        <a href="#problem">The blackout risk</a>
        <a href="#response">How Vidyut helps</a>
        <a href="#platform">Explore the system</a>
      </nav>
      <button className="nav-launch" type="button" onClick={onEnter}>Open interactive demo <span>↗</span></button>
    </header>

    <section className="landing-hero">
      <motion.div className="hero-copy" initial={{ opacity: 0, y: reduced ? 0 : 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .7 }}>
        <div className="system-line"><i className={online ? "online" : ""} /><span>Recorded heatwave demo</span><strong>{online ? "See one neighborhood avoid a blackout" : "Ready to replay"}</strong></div>
        <h1>Stop the blackout<br /><em>before</em> your street<br />goes dark.</h1>
        <p>On the hottest evening of the year, electricity use can surge until an entire street loses power. Vidyut spots the danger early, makes small temporary adjustments, and keeps homes and critical medical loads powered.</p>
        <div className="hero-actions">
          <button className="hero-primary" type="button" onClick={onWatch}>See Vidyut stop the blackout <span>▶</span></button>
          <button className="hero-secondary" type="button" onClick={onEnter}>Try the interactive demo <span>→</span></button>
        </div>
        <div className="hero-proof"><span><b>{savedHomes || 70}</b> homes stay powered</span><span><b>{formatNumber(totals?.vidyut.critical_uptime_pct ?? 100, 2)}%</b> critical-load uptime</span><span><b>1 hour</b> control horizon</span></div>
      </motion.div>

      <motion.div className={`hero-twin phase-${activeHeroBeat.id}`} initial={{ opacity: 0, scale: reduced ? 1 : .96 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: .8, delay: .15 }}>
        <div className="hero-twin-head"><span><i />Recorded neighborhood · {heroFrame?.clock ?? "16:45"}</span><strong>{activeHeroBeat.label}</strong></div>
        <div className="hero-model-key" aria-label="3D model key"><span><i className="home" />Small houses</span><span><i className="power" />Neighborhood power units</span><span><i className="care">+</i>Critical facility</span></div>
        {heroSnapshot ? <Network3D snapshot={heroSnapshot} label="Recorded neighborhood power network" selectedDt={heroSelectedDt} onSelect={setSelectedDt} activeTargets={heroActiveTargets} presentation /> : <div className="twin-loading"><i /><span>Loading the neighborhood</span></div>}
        <motion.div key={activeHeroBeat.id} className="hero-story-card" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .35 }}>
          <span>{activeHeroBeat.label}</span>
          <strong>{activeHeroBeat.title}</strong>
          <p>{activeHeroBeat.body}</p>
          <div className="hero-beat-controls" role="group" aria-label="Neighborhood blackout story">
            {heroBeats.map((beat, index) => <button key={beat.id} type="button" className={index === heroBeatIndex ? "active" : ""} onClick={() => setHeroBeatIndex(index)} aria-pressed={index === heroBeatIndex}><i />{beat.id === "surge" ? "Demand rises" : beat.id === "blackout" ? "Without Vidyut" : "With Vidyut"}</button>)}
          </div>
        </motion.div>
        <div className="hero-impact-badge"><span>{activeHeroBeat.id === "surge" ? "What happens next" : activeHeroBeat.id === "blackout" ? "People affected" : "People protected"}</span><strong>{activeHeroBeat.metric}</strong><small>{activeHeroBeat.metricLabel}</small></div>
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
      <motion.figure
        className="failure-scene"
        initial={{ opacity: 0, scale: reduced ? 1 : 1.02 }}
        whileInView={{ opacity: 1, scale: 1 }}
        viewport={{ once: true, amount: .3 }}
        transition={{ duration: .9, ease: [.16, 1, .3, 1] }}
      >
        <div className="scene-frame">
          <Image
            src="/vidyut-grid-preview.png"
            alt="An isometric distribution network at night. Most transformers glow green and their homes are lit. One transformer glows orange, and the houses behind it are dark. A critical facility nearby stays lit."
            width={1656}
            height={932}
            priority
            sizes="(max-width: 1100px) 100vw, 1400px"
          />
          <span className="scene-pin overloaded" style={{ left: "74.5%", top: "17%" }}>
            <i />
            <b>Over its limit<em>protection trips</em></b>
          </span>
          <span className="scene-pin dark" style={{ left: "88%", top: "33%" }}>
            <i />
            <b>Every home behind it<em>goes dark</em></b>
          </span>
          <span className="scene-pin safe" style={{ left: "72%", top: "72%" }}>
            <i />
            <b>Critical service<em>must never fail</em></b>
          </span>
        </div>
        <figcaption>
          One transformer past its limit. Seventy homes dark behind it. Nobody chose which — the
          equipment simply tripped.
        </figcaption>
      </motion.figure>

      <div className="failure-sequence">
        <article><span>16:15</span><i className="heat-symbol">☀</i><strong>Heatwave demand rises</strong><p>Cooling demand pushes one locality toward its equipment limit.</p></article>
        <b>→</b>
        <article className="danger"><span>16:30</span><i>!</i><strong>{formatNumber(overloadDt?.loading_pct ?? 103.1)}% loaded</strong><p>The transformer is already beyond its rated capacity.</p></article>
        <b>→</b>
        <article className="blackout"><span>16:45</span><i>×</i><strong>Transformer disconnected</strong><p>Protection saves the equipment by taking the whole locality offline.</p></article>
      </div>
    </section>

    <section className="blackout-comparison">
      <div className="comparison-copy">
        <span className="landing-kicker">SAME DEMAND · DIFFERENT CONTROL</span>
        <h2>One event. Two outcomes.</h2>
        <p>
          {divergence
            ? `At ${divergence.clock} on transformer ${divergence.dtId}, conventional protection has already disconnected the locality. Vidyut acted within its one-hour control horizon and kept every home on.`
            : "At the same recorded moment, conventional protection has disconnected the locality. Vidyut acted earlier and keeps it energised."}
        </p>
      </div>

      <div className="outcome-pair">
        <article className="outcome baseline">
          <header><span>Today&apos;s protection</span><i /></header>
          <Neighborhood dark={divergence?.baselineDark ?? 70} label="BASELINE" />
          <footer>
            <strong>{divergence?.baselineDark ?? 70}</strong>
            <span>of 70 homes without power</span>
          </footer>
        </article>

        <div className="outcome-divider"><span>same</span><b>VS</b><span>demand</span></div>

        <article className="outcome vidyut">
          <header><span>With Vidyut</span><i /></header>
          <Neighborhood dark={divergence?.vidyutDark ?? 0} label="VIDYUT" />
          <footer>
            <strong>{divergence?.vidyutDark ?? 0}</strong>
            <span>
              of 70 homes without power
              {divergence ? ` · transformer at ${formatNumber(divergence.vidyutLoad, 0)}%` : ""}
            </span>
          </footer>
        </article>
      </div>

      <div className="protected-service"><i>+</i><span><small>Critical service on this network</small><strong>Critical medical loads remain powered</strong></span><b>PROTECTED</b></div>
    </section>

    <section className="response-section" id="response">
      <div className="section-intro split"><div><span className="landing-kicker">02 / AUTONOMOUS RESPONSE</span><h2>Intervene early.<br />Escalate carefully.</h2></div><p>Vidyut does not jump from forecast to disconnection. It follows an ordered response ladder, records who was affected, and verifies whether the action worked.</p></div>
      <div className="response-loop">
        {loop.map(([number, title, body], index) => <motion.article key={title} initial={{ opacity: 0, y: reduced ? 0 : 18 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, amount: .4 }} transition={{ delay: index * .08 }}><span>{number}</span><div className="loop-icon"><i /></div><strong>{title}</strong><p>{body}</p></motion.article>)}
      </div>
      <div className="response-evidence">
        <div><span>Forecast control horizon</span><strong>4 intervals</strong><small>one hour ahead</small></div>
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
          <div className="preview-kpis"><span><small>Power flow</small><strong>Converged</strong></span><span><small>Control horizon</small><strong>1 hour</strong></span><span><small>Dark-home minutes avoided</small><strong>{formatNumber((totals?.baseline.homes_dark_minutes ?? 0) - (totals?.vidyut.homes_dark_minutes ?? 0), 0)}</strong></span><span><small>Critical-load uptime</small><strong>{formatNumber(totals?.vidyut.critical_uptime_pct ?? 100, 2)}%</strong></span></div>
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
