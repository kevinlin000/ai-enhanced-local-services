import type { AgentShop } from "./agentTypes";
import { agentFinalPayloadFromEvent } from "./agentResponse";
import type { AgentBookingDraft, AgentComparisonRow, AgentStreamEvent, AgentTransaction } from "./agentStream";

export type AgentToolStepStatus = "active" | "done";

export type AgentToolStep = {
  name: string;
  label: string;
  status: AgentToolStepStatus;
};

export type AgentChatMessage = {
  role: "user" | "ai";
  content: string;
  toolsUsed?: string[];
  toolSteps?: AgentToolStep[];
  statusLabel?: string;
  streamMode?: "legacy" | "lifecycle";
  finalEventHandled?: boolean;
  done?: boolean;
  query?: string;
  hasShops?: boolean;
  shops?: AgentShop[];
  transaction?: AgentTransaction;
  bookingDraft?: AgentBookingDraft;
  scopeNote?: string;
  comparisonRows?: AgentComparisonRow[];
  hits?: {
    shop_id: number;
    name: string;
    district: string;
  }[];
};

const DEFAULT_TOOL_LABELS: Record<string, string> = {
  search_shops_by_mrt: "搜尋捷運附近",
  semantic_shop_search: "比對餐廳資料",
  create_hot_seat_order: "建立 Hot Seat 訂單",
  create_booking: "檢查並建立訂位",
  pay_booking_with_test_card: "確認訂金付款",
  cancel_booking: "取消訂位",
  update_booking: "修改訂位",
  create_booking_incident: "建立救場通知",
};

const DEFAULT_STATUS_LABELS = {
  agent_start: "準備處理需求",
  turn_start: "正在理解你的需求",
  tool_execution_start: "正在查詢資料",
  tool_execution_end: "資料已取得，正在整理",
  message_update: "正在撰寫回覆",
  agent_end: "已完成",
  agent_error: "處理失敗",
} as const;

type AgentStatusLabels = Record<keyof typeof DEFAULT_STATUS_LABELS, string>;

type AgentMessageOptions = {
  toolLabels?: Record<string, string>;
  statusLabels?: Partial<AgentStatusLabels>;
  errorMessage?: string;
};

export function agentToolLabel(name: string, labels?: Record<string, string>): string {
  return labels?.[name] ?? DEFAULT_TOOL_LABELS[name] ?? name.replace(/_/g, " ");
}

export function appendUniqueTool(tools: string[] | undefined, name: string): string[] {
  return [...new Set([...(tools ?? []), name])];
}

export function upsertAgentToolStep(
  steps: AgentToolStep[] | undefined,
  name: string,
  status: AgentToolStepStatus,
  labels?: Record<string, string>,
): AgentToolStep[] {
  const next = [...(steps ?? [])];
  const existingIndex = next.findIndex((step) => step.name === name);
  const item = { name, label: agentToolLabel(name, labels), status };
  if (existingIndex >= 0) {
    next[existingIndex] = item;
  } else {
    next.push(item);
  }
  return next;
}

export function applyAgentStreamEventToMessage(
  message: AgentChatMessage,
  event: AgentStreamEvent,
  options: AgentMessageOptions = {},
): AgentChatMessage {
  if (message.role !== "ai") return message;

  const statusLabels = { ...DEFAULT_STATUS_LABELS, ...options.statusLabels };
  const toolLabels = options.toolLabels;

  switch (event.type) {
    case "agent_start":
      return {
        ...message,
        statusLabel: statusLabels.agent_start,
        streamMode: "lifecycle",
      };

    case "turn_start":
      return {
        ...message,
        statusLabel: statusLabels.turn_start,
        streamMode: "lifecycle",
      };

    case "tool_execution_start":
      return {
        ...message,
        statusLabel: `${statusLabels.tool_execution_start}：${agentToolLabel(event.name, toolLabels)}`,
        streamMode: "lifecycle",
        toolSteps: upsertAgentToolStep(message.toolSteps, event.name, "active", toolLabels),
        toolsUsed: appendUniqueTool(message.toolsUsed, event.name),
      };

    case "tool_execution_end":
      return {
        ...message,
        statusLabel: statusLabels.tool_execution_end,
        streamMode: "lifecycle",
        toolSteps: upsertAgentToolStep(message.toolSteps, event.name, "done", toolLabels),
        toolsUsed: appendUniqueTool(message.toolsUsed, event.name),
      };

    case "message_update":
      return {
        ...message,
        content: `${message.content}${event.content}`,
        statusLabel: statusLabels.message_update,
        streamMode: "lifecycle",
      };

    case "chunk":
      if (message.streamMode === "lifecycle") return message;
      return { ...message, content: `${message.content}${event.content}` };

    case "tool":
      if (message.streamMode === "lifecycle") return message;
      return {
        ...message,
        toolsUsed: appendUniqueTool(message.toolsUsed, event.name),
        toolSteps: upsertAgentToolStep(message.toolSteps, event.name, "done", toolLabels),
      };

    case "agent_end":
    case "done": {
      if (event.type === "done" && message.finalEventHandled) return message;
      const finalPayload = agentFinalPayloadFromEvent(event);
      const shops = finalPayload.shops ?? message.shops;
      return {
        ...message,
        content: event.answer || message.content,
        statusLabel: statusLabels.agent_end,
        toolsUsed: event.tools_used ?? message.toolsUsed,
        shops,
        hasShops: (shops?.length ?? 0) > 0,
        transaction: finalPayload.transaction ?? message.transaction,
        bookingDraft: finalPayload.bookingDraft ?? message.bookingDraft,
        scopeNote: finalPayload.scopeNote ?? message.scopeNote,
        comparisonRows: finalPayload.comparisonRows ?? message.comparisonRows,
        finalEventHandled: true,
        done: true,
      };
    }

    case "agent_error":
    case "error":
      return {
        ...message,
        content: event.message || options.errorMessage || "出錯了，再試一次",
        statusLabel: statusLabels.agent_error,
        done: true,
      };

    case "status":
      return {
        ...message,
        statusLabel: event.message,
      };
  }
}

export function updateLastAiMessage(
  messages: AgentChatMessage[],
  event: AgentStreamEvent,
  options?: AgentMessageOptions,
): AgentChatMessage[] {
  const next = [...messages];
  const last = next[next.length - 1];
  if (!last || last.role !== "ai") return messages;
  const updated = applyAgentStreamEventToMessage(last, event, options);
  if (updated === last) return messages;
  next[next.length - 1] = updated;
  return next;
}
