import Groq from "groq-sdk";

export const runtime = "nodejs";

type ExplainRequest = {
  question?: string;
  scenario?: string;
  clock?: string;
  transformer?: Record<string, string | number | boolean | undefined>;
  metrics?: Record<string, string | number | boolean | undefined>;
  forecast?: { horizon_kw?: number[]; safe_limit_kw?: number; rating_kw?: number } | null;
  events?: Array<{ tier?: number; action?: string; kw?: number; households?: number; reason_code?: string }>;
};

export async function POST(request: Request) {
  if (!process.env.GROQ_API_KEY) return Response.json({ detail: "AI explanation is not configured" }, { status: 503 });

  let input: ExplainRequest;
  try {
    input = await request.json() as ExplainRequest;
  } catch {
    return Response.json({ detail: "Request body must be valid JSON" }, { status: 400 });
  }

  const question = input.question?.trim().slice(0, 300) || "Explain what is happening and why it matters to a resident.";
  const context = JSON.stringify({
    scenario: input.scenario,
    clock: input.clock,
    transformer: input.transformer,
    metrics: input.metrics,
    forecast: input.forecast,
    events: input.events?.slice(0, 8),
  });

  try {
    const client = new Groq({ apiKey: process.env.GROQ_API_KEY, timeout: 12000, maxRetries: 1 });
    const completion = await client.chat.completions.create({
      model: "openai/gpt-oss-20b",
      temperature: 0.2,
      max_completion_tokens: 600,
      reasoning_effort: "low",
      messages: [
        {
          role: "system",
          content: "You explain a simulated Indian electrical distribution-network replay called Vidyut. Use only the supplied context. Begin by making clear that the reading is simulated. Be concrete, calm and understandable to a non-engineer. The transformer equipment rating is 100%; do not describe a lower observed value as its safe limit. A forecast safe_limit_kw is an explicit controller threshold in kW, not a loading percentage. Event targets such as F1-DT17 are local transformer areas, not feeders. The supplied metrics are deliberately curated; do not infer unlisted losses, fairness, temperatures, feeder imbalance, appliance types, or people affected. Never claim live telemetry, recommend an action, or imply you control equipment. Use plain text without Markdown. Answer in at most 80 words and finish every sentence.",
        },
        { role: "user", content: `Question: ${question}\nSimulation context: ${context}` },
      ],
    });
    const explanation = completion.choices[0]?.message?.content?.replaceAll("**", "").trim();
    if (!explanation) return Response.json({ detail: "The AI returned no explanation" }, { status: 502 });
    return Response.json({ explanation, model: "openai/gpt-oss-20b", advisory_only: true });
  } catch {
    return Response.json({ detail: "The AI explanation service is temporarily unavailable" }, { status: 502 });
  }
}
