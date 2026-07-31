import { API_URL } from "../lib/constants";
import { TickMessage } from "../types";

export function connectSimulationWebSocket(
  runId: string,
  speed: number,
  onTick: (tick: TickMessage) => void,
  onComplete: () => void,
  onError: (err: Event) => void
): WebSocket {
  const wsUrl = API_URL.replace(/^http/, "ws") + `/ws/runs/${runId}?speed=${speed}`;
  const ws = new WebSocket(wsUrl);

  ws.onmessage = (evt) => {
    try {
      const msg: TickMessage = JSON.parse(evt.data);
      if (msg.type === "tick") {
        onTick(msg);
      } else if (msg.type === "complete") {
        onComplete();
      }
    } catch {
      // Ignore non-json or malformed
    }
  };

  ws.onerror = onError;
  return ws;
}
