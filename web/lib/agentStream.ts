export type AgentTransaction = {
  kind: "booking";
  success: boolean;
  status: "CONFIRMED" | "PAID" | "PENDING_PAYMENT" | "PAYMENT_FAILED" | "FAILED" | "EXPIRED";
  shop_id?: number | null;
  shop_name?: string | null;
  booking_code?: string | null;
  people?: number | null;
  date?: string | null;
  time?: string | null;
  table_type?: string | null;
  needs_deposit?: boolean;
  deposit_total?: number | null;
  hold_expires_at?: string | null;
  hold_minutes?: number | null;
  rec_trade_id?: string | null;
  payment_amount?: number | null;
  payment_note?: string | null;
  error?: string | null;
};

export type AgentStreamEvent =
  | { type: "agent_start"; session_id?: string }
  | { type: "turn_start"; query: string; session_id?: string }
  | { type: "tool_execution_start"; name: string; args?: Record<string, unknown>; session_id?: string }
  | { type: "tool_execution_end"; name: string; result_summary?: Record<string, unknown>; session_id?: string }
  | { type: "message_update"; content: string }
  | {
      type: "agent_end";
      answer: string;
      recommended_shop_ids?: number[];
      narrative?: string;
      rejected_shop_ids?: number[];
      rejection_summary?: string | null;
      transaction?: AgentTransaction | null;
      tools_used?: string[];
      tool_result?: unknown;
      session_id?: string;
    }
  | { type: "agent_error"; message: string; session_id?: string }
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
      transaction?: AgentTransaction | null;
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
