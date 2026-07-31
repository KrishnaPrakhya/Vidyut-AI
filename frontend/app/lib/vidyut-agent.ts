import "server-only";

import { HumanMessage, SystemMessage } from "@langchain/core/messages";
import { ChatGroq } from "@langchain/groq";
import { END, START, StateGraph, StateSchema } from "@langchain/langgraph";
import { z } from "zod/v4";

const IntentSchema = z.enum(["risk", "compare", "resident", "incident", "general"]);
const AudienceSchema = z.enum(["operator", "resident", "reviewer"]);

const EventSchema = z.object({
  tier: z.number().int().min(0).max(3).optional(),
  action: z.string().max(80).optional(),
  target: z.string().max(80).optional(),
  kw: z.number().finite().optional(),
  households: z.number().int().min(0).optional(),
  reason_code: z.string().max(120).optional(),
});

const CopilotContextSchema = z.object({
  scenario: z.enum(["normal", "heatwave", "ev_surge"]),
  clock: z.string().regex(/^\d{2}:\d{2}$/),
  transformer: z.object({
    id: z.string().min(1).max(80),
    baseline_loading_pct: z.number().finite().optional(),
    vidyut_loading_pct: z.number().finite().optional(),
    baseline_homes_dark: z.number().int().min(0).optional(),
    vidyut_homes_dark: z.number().int().min(0).optional(),
  }),
  metrics: z.object({
    baseline_network_max_loading_pct: z.number().finite().optional(),
    vidyut_network_max_loading_pct: z.number().finite().optional(),
    vidyut_homes_dark: z.number().int().min(0).optional(),
    vidyut_critical_uptime_pct: z.number().finite().optional(),
    vidyut_power_flow_converged: z.boolean().optional(),
  }),
  forecast: z.object({
    horizon_kw: z.array(z.number().finite()).max(12).optional(),
    safe_limit_kw: z.number().finite().optional(),
    rating_kw: z.number().finite().optional(),
  }).nullable().optional(),
  events: z.array(EventSchema).max(20).default([]),
});

export const CopilotRequestSchema = CopilotContextSchema.extend({
  question: z.string().trim().min(2).max(300),
});

const EvidenceSchema = z.object({
  id: z.string(),
  label: z.string(),
  value: z.string(),
  source: z.string(),
});

const TraceSchema = z.object({
  node: z.string(),
  label: z.string(),
  detail: z.string(),
  status: z.enum(["complete", "corrected"]),
});

const ValidationSchema = z.object({
  valid: z.boolean(),
  issues: z.array(z.string()),
});

const AgentState = new StateSchema({
  question: z.string(),
  context: CopilotContextSchema,
  intent: IntentSchema.default("general"),
  audience: AudienceSchema.default("operator"),
  evidence: z.array(EvidenceSchema).default([]),
  usedEvidenceIds: z.array(z.string()).default([]),
  answer: z.string().default(""),
  validation: ValidationSchema.default({ valid: false, issues: [] }),
  trace: z.array(TraceSchema).default([]),
});

export type CopilotRequest = z.infer<typeof CopilotRequestSchema>;
export type CopilotEvidence = z.infer<typeof EvidenceSchema>;
export type CopilotTrace = z.infer<typeof TraceSchema>;
export type CopilotIntent = z.infer<typeof IntentSchema>;

export type CopilotResult = {
  explanation: string;
  intent: CopilotIntent;
  audience: z.infer<typeof AudienceSchema>;
  confidence: "high" | "medium";
  evidence: CopilotEvidence[];
  trace: CopilotTrace[];
  model: string;
  advisory_only: true;
};

const PlanSchema = z.object({
  intent: IntentSchema,
  audience: AudienceSchema,
});

const DraftSchema = z.object({
  answer: z.string().min(1),
  evidence_ids: z.array(z.string()).min(1).max(10),
});

const MODEL = "openai/gpt-oss-20b";

function model(maxTokens: number) {
  return new ChatGroq({
    model: MODEL,
    apiKey: process.env.GROQ_API_KEY,
    temperature: 0.1,
    maxTokens,
    maxRetries: 1,
    timeout: 12000,
    reasoningEffort: "low",
  });
}

function number(value: number | undefined, suffix = "") {
  return value === undefined ? "Unavailable" : `${new Intl.NumberFormat("en-IN", { maximumFractionDigits: 1 }).format(value)}${suffix}`;
}

function buildEvidence(context: z.infer<typeof CopilotContextSchema>): CopilotEvidence[] {
  const evidence: CopilotEvidence[] = [
    { id: "baseline-local-loading", label: "Baseline locality", value: number(context.transformer.baseline_loading_pct, "%"), source: `${context.clock} recorded baseline frame` },
    { id: "vidyut-local-loading", label: "Vidyut locality", value: number(context.transformer.vidyut_loading_pct, "%"), source: `${context.clock} recorded Vidyut frame` },
    { id: "baseline-homes-dark", label: "Baseline homes dark", value: number(context.transformer.baseline_homes_dark), source: `${context.transformer.id} baseline state` },
    { id: "vidyut-homes-dark", label: "Vidyut homes dark", value: number(context.transformer.vidyut_homes_dark), source: `${context.transformer.id} Vidyut state` },
    { id: "baseline-network-max", label: "Baseline network maximum", value: number(context.metrics.baseline_network_max_loading_pct, "%"), source: `${context.clock} baseline network metrics` },
    { id: "vidyut-network-max", label: "Vidyut network maximum", value: number(context.metrics.vidyut_network_max_loading_pct, "%"), source: `${context.clock} Vidyut network metrics` },
    { id: "critical-uptime", label: "Critical uptime", value: number(context.metrics.vidyut_critical_uptime_pct, "%"), source: `${context.clock} Vidyut network metrics` },
    { id: "power-flow", label: "Power flow", value: context.metrics.vidyut_power_flow_converged === undefined ? "Unavailable" : context.metrics.vidyut_power_flow_converged ? "Converged" : "Not converged", source: `${context.clock} Vidyut solver status` },
  ];

  if (context.forecast?.safe_limit_kw !== undefined) {
    evidence.push({ id: "forecast-limit", label: "Forecast control limit", value: number(context.forecast.safe_limit_kw, " kW"), source: `${context.transformer.id} forecast snapshot` });
  }
  if (context.events.length) {
    const reduction = context.events.reduce((sum, event) => sum + (event.kw ?? 0), 0);
    const households = context.events.reduce((sum, event) => sum + (event.households ?? 0), 0);
    evidence.push({ id: "recorded-actions", label: "Actions this interval", value: `${context.events.length} ${context.events.length === 1 ? "record" : "records"} · ${number(reduction, " kW")} · ${number(households)} household actions`, source: `${context.clock} controller event log` });
    const actionCounts = new Map<string, number>();
    for (const event of context.events) {
      const label = event.action?.replaceAll("_", " ") ?? "unlabelled";
      actionCounts.set(label, (actionCounts.get(label) ?? 0) + 1);
    }
    const mix = Array.from(actionCounts, ([label, count]) => `${label} ${count}`).join(" · ");
    evidence.push({ id: "action-mix", label: "Recorded action mix", value: mix, source: `${context.clock} controller event categories` });
  }
  return evidence;
}

function fallbackPlan(question: string): z.infer<typeof PlanSchema> {
  const normalized = question.toLowerCase();
  if (/resident|household|customer|public|message/.test(normalized)) return { intent: "resident", audience: "resident" };
  if (/incident|report|brief|timeline|summary/.test(normalized)) return { intent: "incident", audience: "reviewer" };
  if (/compare|baseline|changed|difference|versus|vs\b/.test(normalized)) return { intent: "compare", audience: "operator" };
  if (/risk|why|overload|limit|danger|transformer/.test(normalized)) return { intent: "risk", audience: "operator" };
  return { intent: "general", audience: "operator" };
}

function textContent(content: unknown) {
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return "";
  return content.map((part) => typeof part === "string" ? part : typeof part === "object" && part && "text" in part ? String(part.text) : "").join(" ");
}

const groundNode: typeof AgentState.Node = (state) => ({
  evidence: buildEvidence(state.context),
  trace: [...state.trace, { node: "ground_context", label: "Ground context", detail: `${state.context.transformer.id} · ${state.context.clock} · curated simulation fields only`, status: "complete" }],
});

const planNode: typeof AgentState.Node = async (state) => {
  let plan = fallbackPlan(state.question);
  let detail = `Deterministic fallback selected ${plan.intent}`;
  try {
    const planner = model(260).withStructuredOutput(PlanSchema, { name: "vidyut_copilot_plan" });
    plan = await planner.invoke([
      new SystemMessage("Classify the request for a simulated grid copilot. Choose risk for equipment-risk explanations, compare for baseline-versus-Vidyut questions, resident for plain public communication, incident for an audit-style event brief, and general otherwise. Do not answer the request."),
      new HumanMessage(state.question),
    ]);
    detail = `Routed to ${plan.intent} specialist for a ${plan.audience} audience`;
  } catch {
    detail = `Planner unavailable; bounded router selected ${plan.intent}`;
  }
  return {
    ...plan,
    trace: [...state.trace, { node: "plan_request", label: "Plan request", detail, status: "complete" }],
  };
};

const specialistGuidance: Record<CopilotIntent, string> = {
  risk: "Explain why the selected transformer area is or is not at risk. Treat 100% loading as the equipment rating. Distinguish current loading from a kW forecast control limit.",
  compare: "Compare the baseline and Vidyut outcomes directly. Describe differences between percentage readings as percentage points, not percent decreases. State only differences supported by the evidence and explain why the difference matters.",
  resident: "Write a calm resident-facing explanation. Describe recorded controller events as simulated actions, avoid technical jargon, and do not imply that a specific appliance or person was controlled unless explicitly listed.",
  incident: "Write a compact incident brief in this order: observed condition, simulated controller response, outcome, and evidence limitation. Do not invent a chronology outside the supplied interval.",
  general: "Answer the question using the smallest relevant subset of evidence and clearly distinguish observations, forecasts, and controller-event records.",
};

function specialistNode(intent: CopilotIntent): typeof AgentState.Node {
  return async (state) => {
    const system = `You are Vidyut Copilot, an advisory analyst for a simulated Indian electrical-distribution replay. ${specialistGuidance[intent]} Use only the supplied evidence. Start by saying this is a simulated reading. Never claim live telemetry, invent causes or affected people, recommend or issue an actuation command, or imply that you control equipment. Event targets such as F1-DT17 are local transformer areas, not feeders. Repeat a metric as being at its recorded value; never describe it as below or above that same value. Use plain text without Markdown, at most 90 words, and finish every sentence. Return the exact IDs of every evidence record used; do not cite an unused record.`;
    const input = JSON.stringify({ question: state.question, audience: state.audience, frame: { scenario: state.context.scenario, clock: state.context.clock, transformer_id: state.context.transformer.id }, evidence: state.evidence });
    let answer = "";
    let usedEvidenceIds: string[] = [];
    try {
      const drafter = model(800).withStructuredOutput(DraftSchema, { name: `vidyut_${intent}_draft` });
      const draft = await drafter.invoke([new SystemMessage(system), new HumanMessage(input)]);
      answer = draft.answer.replaceAll("**", "").trim();
      const knownIds = new Set(state.evidence.map((item) => item.id));
      usedEvidenceIds = Array.from(new Set(draft.evidence_ids.filter((id) => knownIds.has(id))));
    } catch {
      const response = await model(700).invoke([new SystemMessage(system), new HumanMessage(input)]);
      answer = textContent(response.content).replaceAll("**", "").trim();
      usedEvidenceIds = state.evidence.map((item) => item.id);
    }
    if (!answer) throw new Error("The specialist returned no answer");
    return {
      answer,
      usedEvidenceIds,
      trace: [...state.trace, { node: `${intent}_specialist`, label: `${intent[0].toUpperCase()}${intent.slice(1)} specialist`, detail: `Drafted with ${usedEvidenceIds.length} cited evidence records`, status: "complete" }],
    };
  };
}

function allowedNumbers(state: typeof AgentState.State) {
  const values: number[] = [];
  const used = new Set(state.usedEvidenceIds);
  for (const item of state.evidence) {
    if (!used.has(item.id)) continue;
    values.push(...Array.from(item.value.matchAll(/-?\d+(?:\.\d+)?/g), (match) => Number(match[0])));
  }
  const baseValues = [...values];
  for (let left = 0; left < baseValues.length; left += 1) {
    for (let right = left + 1; right < baseValues.length; right += 1) {
      values.push(Number(Math.abs(baseValues[left] - baseValues[right]).toFixed(1)));
    }
  }
  values.push(100);
  return values;
}

function validateAnswer(state: typeof AgentState.State, answer = state.answer) {
  const issues: string[] = [];
  if (!state.usedEvidenceIds.length) issues.push("The answer must cite at least one known evidence record");
  if (!/simulat/i.test(answer)) issues.push("The answer must identify the reading as simulated");
  if (/\*\*|^#{1,6}\s|```/m.test(answer)) issues.push("Markdown formatting is not allowed");
  if (/\b(?:i|we|vidyut ai|copilot)\s+(?:will|can)\s+(?:disconnect|curtail|shed|switch|dispatch|control|reduce)\b/i.test(answer)) issues.push("The answer implies actuation authority");
  const allowed = allowedNumbers(state);
  const numericText = answer.replace(/[A-Z]\d+-DT\d+/gi, "").replace(/\b\d{2}:\d{2}\b/g, "");
  const stated = Array.from(numericText.matchAll(/-?\d+(?:\.\d+)?/g), (match) => Number(match[0]));
  const unsupported = stated.filter((value) => !allowed.some((candidate) => Math.abs(candidate - value) < 0.051));
  if (unsupported.length) issues.push(`Unsupported numeric claims: ${Array.from(new Set(unsupported)).join(", ")}`);
  return { valid: issues.length === 0, issues };
}

function referencedEvidenceIds(state: typeof AgentState.State, answer = state.answer) {
  const normalized = answer.toLowerCase();
  const selected = new Set(state.usedEvidenceIds);
  const genericWords = new Set(["baseline", "vidyut", "recorded", "network", "interval"]);
  const numericText = answer.replace(/[A-Z]\d+-DT\d+/gi, "").replace(/\b\d{2}:\d{2}\b/g, "");
  const answerNumbers = Array.from(numericText.matchAll(/-?\d+(?:\.\d+)?/g), (match) => Number(match[0]));
  return state.evidence.filter((item) => {
    if (!selected.has(item.id)) return false;
    const labelWords = item.label.toLowerCase().split(/\W+/).filter((word) => word.length >= 5 && !genericWords.has(word));
    const labelMatch = labelWords.some((word) => normalized.includes(word));
    const textValues = item.value.toLowerCase().split(/[^a-z]+/).filter((word) => word.length >= 5);
    const valueMatch = textValues.some((word) => normalized.includes(word));
    const itemNumbers = Array.from(item.value.matchAll(/-?\d+(?:\.\d+)?/g), (match) => Number(match[0]));
    const numericMatch = itemNumbers.some((value) => answerNumbers.some((candidate) => Math.abs(candidate - value) < 0.051));
    return labelMatch || valueMatch || numericMatch;
  }).map((item) => item.id);
}

const verifyNode: typeof AgentState.Node = (state) => {
  const usedEvidenceIds = referencedEvidenceIds(state);
  const verifiedState = { ...state, usedEvidenceIds };
  const validation = validateAnswer(verifiedState);
  const citationsAdjusted = usedEvidenceIds.length !== state.usedEvidenceIds.length;
  return {
    usedEvidenceIds,
    validation,
    trace: [...state.trace, { node: "verify_claims", label: "Verify claims", detail: validation.valid ? `${usedEvidenceIds.length} citations matched · authority and numeric claims passed` : validation.issues.join(" · "), status: validation.valid && !citationsAdjusted ? "complete" : "corrected" }],
  };
};

function deterministicAnswer(state: typeof AgentState.State) {
  const transformer = state.context.transformer;
  const baseline = number(transformer.baseline_loading_pct, "%");
  const vidyut = number(transformer.vidyut_loading_pct, "%");
  const baselineDark = number(transformer.baseline_homes_dark);
  const vidyutDark = number(transformer.vidyut_homes_dark);
  if (state.intent === "resident") return `This is a simulated reading for ${transformer.id}. The baseline shows ${baselineDark} homes dark, while the Vidyut replay shows ${vidyutDark}. Recorded controller events are advisory evidence from the simulation, not live commands.`;
  if (state.intent === "incident") return `This is a simulated incident brief for ${state.context.clock}. ${transformer.id} reaches ${baseline} in the baseline and ${vidyut} with Vidyut. Homes dark change from ${baselineDark} to ${vidyutDark}. The statement is limited to this recorded interval.`;
  return `This is a simulated reading for ${transformer.id}. Baseline loading is ${baseline}, compared with ${vidyut} in the Vidyut replay. Homes dark are ${baselineDark} in the baseline and ${vidyutDark} with Vidyut. The copilot is advisory and cannot operate grid equipment.`;
}

const repairNode: typeof AgentState.Node = async (state) => {
  let answer = deterministicAnswer(state);
  let usedEvidenceIds = state.evidence.map((item) => item.id);
  try {
    const response = await model(650).invoke([
      new SystemMessage("Repair the draft so every number appears in the supplied evidence, it explicitly says the reading is simulated, it contains no Markdown, and it never implies actuation authority. Preserve the requested audience and return only the repaired answer in at most 80 words."),
      new HumanMessage(JSON.stringify({ draft: state.answer, issues: state.validation.issues, evidence: state.evidence })),
    ]);
    const candidate = textContent(response.content).replaceAll("**", "").trim();
    if (candidate) answer = candidate;
  } catch {
    answer = deterministicAnswer(state);
  }
  usedEvidenceIds = referencedEvidenceIds({ ...state, usedEvidenceIds }, answer);
  let repairedState = { ...state, usedEvidenceIds };
  let validation = validateAnswer(repairedState, answer);
  if (!validation.valid) {
    answer = deterministicAnswer(state);
    usedEvidenceIds = referencedEvidenceIds({ ...state, usedEvidenceIds: state.evidence.map((item) => item.id) }, answer);
    repairedState = { ...state, usedEvidenceIds };
    validation = validateAnswer(repairedState, answer);
  }
  return {
    answer,
    usedEvidenceIds,
    validation,
    trace: [...state.trace, { node: "repair_answer", label: "Repair answer", detail: "Rewrote the draft against the evidence allow-list", status: "corrected" }],
  };
};

const finalizeNode: typeof AgentState.Node = (state) => ({
  answer: state.answer.trim(),
  trace: [...state.trace, { node: "finalize", label: "Finalize", detail: "Advisory response packaged with evidence and audit trace", status: "complete" }],
});

function routeIntent(state: typeof AgentState.State) {
  return state.intent;
}

function routeValidation(state: typeof AgentState.State) {
  return state.validation.valid ? "finalize" : "repair_answer";
}

const graph = new StateGraph(AgentState)
  .addNode("ground_context", groundNode)
  .addNode("plan_request", planNode)
  .addNode("risk_specialist", specialistNode("risk"))
  .addNode("compare_specialist", specialistNode("compare"))
  .addNode("resident_specialist", specialistNode("resident"))
  .addNode("incident_specialist", specialistNode("incident"))
  .addNode("general_specialist", specialistNode("general"))
  .addNode("verify_claims", verifyNode)
  .addNode("repair_answer", repairNode)
  .addNode("finalize", finalizeNode)
  .addEdge(START, "ground_context")
  .addEdge("ground_context", "plan_request")
  .addConditionalEdges("plan_request", routeIntent, {
    risk: "risk_specialist",
    compare: "compare_specialist",
    resident: "resident_specialist",
    incident: "incident_specialist",
    general: "general_specialist",
  })
  .addEdge("risk_specialist", "verify_claims")
  .addEdge("compare_specialist", "verify_claims")
  .addEdge("resident_specialist", "verify_claims")
  .addEdge("incident_specialist", "verify_claims")
  .addEdge("general_specialist", "verify_claims")
  .addConditionalEdges("verify_claims", routeValidation, {
    finalize: "finalize",
    repair_answer: "repair_answer",
  })
  .addEdge("repair_answer", "finalize")
  .addEdge("finalize", END)
  .compile();

export async function runVidyutCopilot(input: CopilotRequest): Promise<CopilotResult> {
  const context = CopilotContextSchema.parse(input);
  const result = await graph.invoke({ question: input.question, context });
  return {
    explanation: result.answer,
    intent: result.intent,
    audience: result.audience,
    confidence: result.validation.valid && !result.trace.some((step) => step.status === "corrected") ? "high" : "medium",
    evidence: result.evidence.filter((item) => result.usedEvidenceIds.includes(item.id)),
    trace: result.trace,
    model: MODEL,
    advisory_only: true,
  };
}
