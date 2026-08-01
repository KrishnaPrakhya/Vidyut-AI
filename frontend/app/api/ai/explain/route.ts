import { CopilotRequestSchema, runVidyutCopilot } from "../../../lib/vidyut-agent";

export const runtime = "nodejs";

export async function POST(request: Request) {
  if (!process.env.GROQ_API_KEY) {
    return Response.json({ detail: "Vidyut Copilot is not configured" }, { status: 503 });
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return Response.json({ detail: "Request body must be valid JSON" }, { status: 400 });
  }

  const parsed = CopilotRequestSchema.safeParse(body);
  if (!parsed.success) {
    return Response.json({ detail: "The copilot context is incomplete or invalid", issues: parsed.error.issues.map((issue) => issue.path.join(".")) }, { status: 422 });
  }

  const started = performance.now();
  try {
    const result = await runVidyutCopilot(parsed.data);
    return Response.json({ ...result, orchestrator: "langgraph", duration_ms: Math.round(performance.now() - started) });
  } catch {
    return Response.json({ detail: "Vidyut Copilot is temporarily unavailable" }, { status: 502 });
  }
}
