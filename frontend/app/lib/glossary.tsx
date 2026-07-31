"use client";

import { useState, type ReactNode } from "react";

export type Term = { short: string; long: string; note?: string };

export const GLOSSARY: Record<string, Term> = {
  transformer: {
    short: "The box that feeds your street",
    long: "A distribution transformer steps high-voltage electricity down to the voltage homes use. Each one here serves about 70 homes.",
    note: "When it overheats, the traditional fix is to cut power to every home behind it.",
  },
  feeder: {
    short: "A cable serving many streets",
    long: "The medium-voltage line running out of the substation. Each of the three feeders here carries 20 transformers.",
  },
  loading: {
    short: "How hard equipment is working",
    long: "The share of rated capacity in use. 100% is the design limit; beyond it the equipment overheats and its life shortens.",
    note: "Heat is what destroys transformers, which is why this number matters.",
  },
  baseline: {
    short: "How the grid is run today",
    long: "If a transformer stays over its limit for two consecutive 15-minute readings, power is cut to the whole transformer for 45 minutes.",
    note: "Blunt, but it is what actually happens.",
  },
  vidyut: {
    short: "The system being tested",
    long: "Forecasts each transformer an hour ahead, then shifts flexible appliances, reroutes the network, and interrupts supply only as a last resort.",
  },
  unserved: {
    short: "Electricity people wanted but did not get",
    long: "Demand that was never met, in kilowatt-hours. It converts directly into money at the tariff.",
  },
  homesDark: {
    short: "Homes with no power, times how long",
    long: "Measured in household-minutes. Ten homes off for thirty minutes is 300 household-minutes.",
    note: "It captures both how many people were affected and for how long.",
  },
  criticalUptime: {
    short: "Power kept on where it must never fail",
    long: "About 2% of homes are marked critical — someone dependent on a medical device, for instance. This is the share of time they stayed powered.",
    note: "Vidyut must read exactly 100%. A test fails the build if it ever does not.",
  },
  curtailment: {
    short: "Turning something down, not off",
    long: "Briefly reducing one appliance rather than cutting the whole home. An air conditioner easing off for thirty minutes is curtailment; a dark house is not.",
  },
  fairness: {
    short: "A record of who has been asked to give up what",
    long: "Every intervention is written against the household that bore it, weighted by severity: curtailment 1x, a supply ceiling 2x, an interruption 4x.",
    note: "Without it, the same few homes get asked every single day.",
  },
  gini: {
    short: "How evenly a burden is shared",
    long: "0 means everyone bore the same amount; 1 means one household bore everything.",
    note: "Read it carefully — cutting a whole transformer scores well, because everyone suffers equally.",
  },
  tieSwitch: {
    short: "A normally-open link between feeders",
    long: "A switch that can join two feeders. Closing one and opening another moves part of the network onto a less loaded cable.",
  },
  reconfiguration: {
    short: "Rerouting the network",
    long: "Choosing which switches are open so load spreads more evenly. The network must stay radial: every transformer fed by exactly one path.",
    note: "Nobody is asked to use less. Only the route changes.",
  },
  addressable: {
    short: "Homes the system can actually reach",
    long: "A home is addressable if it has a controllable device, or a smart meter that can enforce a load limit. Everyone else can only be sent a price signal.",
    note: "Smart meters provide visibility. Connected devices provide control. They are not the same thing.",
  },
  forecast: {
    short: "What load is expected next hour",
    long: "A prediction of each transformer's load over the coming hour, so action can be taken before the limit is crossed rather than after.",
  },
  safeLimit: {
    short: "The line to act before crossing",
    long: "90% of the transformer's rating. Acting here leaves margin; waiting for 100% means acting too late.",
  },
  spread: {
    short: "Gap between busiest and quietest feeder",
    long: "The difference in loading between the most and least loaded cable. A wide gap means one strains while another sits idle.",
  },
  registered: {
    short: "Capacity we know exists",
    long: "The rated power of controllable devices actually installed. A fact about hardware, not an estimate.",
  },
  estimated: {
    short: "Inferred from meter and weather data",
    long: "How much load appears to move with temperature. A statistical estimate, reported with a confidence level.",
  },
  actionable: {
    short: "Estimated, capped by what exists",
    long: "You cannot act on capacity you do not have. Where the estimate exceeds registered capacity, the registered figure wins.",
  },
  verified: {
    short: "Measured after the event",
    long: "What the reduction actually turned out to be, using the high-4-of-5 method utilities use for demand response.",
  },
  interval: {
    short: "15 simulated minutes",
    long: "The day advances in 15-minute steps, 96 of them. That is the interval Indian meters record and tariffs settle on.",
  },
};

export function Term({ k, children }: { k: keyof typeof GLOSSARY; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const entry = GLOSSARY[k];
  if (!entry) return <>{children}</>;

  return (
    <span
      className="term"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
      tabIndex={0}
      role="button"
      aria-label={`${String(children)}: ${entry.short}`}
    >
      {children}
      {open && (
        <span className="term-card" role="tooltip">
          <strong>{entry.short}</strong>
          <span>{entry.long}</span>
          {entry.note && <em>{entry.note}</em>}
        </span>
      )}
    </span>
  );
}
