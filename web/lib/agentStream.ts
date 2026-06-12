export type AgentTransaction = {
  kind: "booking";
  success: boolean;
  status: "CONFIRMED" | "PAID" | "PENDING_PAYMENT" | "PAYMENT_FAILED" | "FAILED" | "EXPIRED" | "CANCELED";
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
  driving_to_booking?: boolean;
  parking_reminder_enabled?: boolean;
  parking_reminder_sent_at?: string | null;
  error?: string | null;
};

export type AgentBookingDraft = {
  shop_id: number;
  shop_name: string;
  people?: number | null;
  date?: string | null;
  time?: string | null;
  table_type?: string | null;
};

export type AgentComparisonRow = {
  shop_id?: number | string | null;
  name?: string | null;
  feature_highlight?: string | null;
  best_for?: string | null;
  booking_status?: string | null;
  meta?: string | null;
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
      recommended_shop_ids?: Array<number | string>;
      narrative?: string;
      rejected_shop_ids?: number[];
      rejection_summary?: string | null;
      scope_note?: string | null;
      transaction?: AgentTransaction | null;
      booking_draft?: AgentBookingDraft | null;
      shops?: unknown;
      comparison_rows?: AgentComparisonRow[] | null;
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
      recommended_shop_ids?: Array<number | string>;
      narrative?: string;
      rejected_shop_ids?: number[];
      rejection_summary?: string | null;
      scope_note?: string | null;
      transaction?: AgentTransaction | null;
      booking_draft?: AgentBookingDraft | null;
      shops?: unknown;
      comparison_rows?: AgentComparisonRow[] | null;
      tools_used?: string[];
      tool_result?: unknown;
      session_id?: string;
    }
  | { type: "error"; message: string };

type AgentResponse = {
  answer?: string;
  recommended_shop_ids?: Array<number | string>;
  narrative?: string;
  rejected_shop_ids?: number[];
  rejection_summary?: string | null;
  scope_note?: string | null;
  transaction?: AgentTransaction | null;
  booking_draft?: AgentBookingDraft | null;
  shops?: unknown;
  comparison_rows?: AgentComparisonRow[] | null;
  tools_used?: string[];
  tool_result?: unknown;
  session_id?: string;
};

function isTerminalEvent(event: AgentStreamEvent): boolean {
  return event.type === "agent_end" || event.type === "done" || event.type === "agent_error" || event.type === "error";
}

async function fetchAgentFallback(
  body: { query: string; session_id?: string },
  headers: Record<string, string>,
): Promise<AgentResponse> {
  const res = await fetch("/api/ai/agent", {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<AgentResponse>;
}

export async function streamAgentResponse(
  body: { query: string; session_id?: string },
  onEvent: (event: AgentStreamEvent) => void,
) {
  const token = typeof window !== "undefined" ? window.localStorage.getItem("bytebites_token") : null;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const controller = new AbortController();
  let receivedEvent = false;
  let terminalReceived = false;
  let firstEventTimedOut = false;
  let shouldUseFallback = false;
  let inactivityTimeout: number | null = null;
  const requestFallback = () => {
    shouldUseFallback = true;
    controller.abort();
  };
  const clearInactivityTimeout = () => {
    if (inactivityTimeout != null) {
      window.clearTimeout(inactivityTimeout);
      inactivityTimeout = null;
    }
  };
  const resetInactivityTimeout = () => {
    clearInactivityTimeout();
    inactivityTimeout = window.setTimeout(requestFallback, 12_000);
  };
  const firstEventTimeout = window.setTimeout(() => {
    if (!receivedEvent) {
      firstEventTimedOut = true;
      requestFallback();
    }
  }, 8_000);
  const timeout = window.setTimeout(requestFallback, 45_000);

  const runFallback = async () => {
    const fallback = await fetchAgentFallback(body, headers);
    onEvent({
      type: "agent_end",
      answer: fallback.answer ?? "",
      recommended_shop_ids: fallback.recommended_shop_ids,
      narrative: fallback.narrative,
      rejected_shop_ids: fallback.rejected_shop_ids,
      rejection_summary: fallback.rejection_summary,
      scope_note: fallback.scope_note,
      transaction: fallback.transaction,
      booking_draft: fallback.booking_draft,
      shops: fallback.shops,
      comparison_rows: fallback.comparison_rows,
      tools_used: fallback.tools_used,
      tool_result: fallback.tool_result,
      session_id: fallback.session_id ?? body.session_id,
    });
  };

  try {
    const res = await fetch("/api/ai/agent/stream", {
      method: "POST",
      headers,
      body: JSON.stringify(body),
      signal: controller.signal,
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
          receivedEvent = true;
          window.clearTimeout(firstEventTimeout);
          onEvent(parsed);
          if (isTerminalEvent(parsed)) {
            terminalReceived = true;
            clearInactivityTimeout();
            await reader.cancel().catch(() => {});
            return;
          }
          resetInactivityTimeout();
        } catch {
          // ignore malformed frame
        }
      }
    }

    if (!terminalReceived) {
      shouldUseFallback = true;
      await runFallback();
    }
  } catch (error) {
    if (shouldUseFallback || firstEventTimedOut) {
      await runFallback();
      return;
    }
    throw error;
  } finally {
    window.clearTimeout(firstEventTimeout);
    window.clearTimeout(timeout);
    clearInactivityTimeout();
  }
}
