export type AgentStreamEvent =
  | { type: "status"; message: string }
  | { type: "tool"; name: string }
  | { type: "chunk"; content: string }
  | {
      type: "done";
      answer: string;
      recommended_shop_ids?: number[];
      narrative?: string;
      rejected_shop_ids?: number[];
      rejection_summary?: string | null;
      tools_used?: string[];
      tool_result?: unknown;
      session_id?: string;
    }
  | { type: "error"; message: string };

export async function streamAgentResponse(
  body: { query: string; session_id?: string },
  onEvent: (event: AgentStreamEvent) => void,
) {
  const res = await fetch("/api/ai/agent/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok || !res.body) {
    throw new Error(`${res.status} ${res.statusText}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";

    for (const frame of frames) {
      const line = frame
        .split("\n")
        .find((item) => item.startsWith("data: "));
      if (!line) continue;
      try {
        const parsed = JSON.parse(line.slice(6)) as AgentStreamEvent;
        onEvent(parsed);
      } catch {
        // ignore malformed frame
      }
    }
  }
}
