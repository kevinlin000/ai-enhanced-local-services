# AI Agent Event Contract

ByteBites AI concierge uses Server-Sent Events for the multi-turn agent at
`POST /api/ai/agent/stream`.

The stream keeps the current UI-compatible events (`status`, `tool`, `chunk`,
`done`, `error`) and also emits richer agent lifecycle events. New clients should
prefer the lifecycle events, while existing clients can continue using the
legacy events.

## Lifecycle Events

| Event type | When it is emitted | Key fields |
| --- | --- | --- |
| `agent_start` | A request is accepted and the agent begins a turn. | `session_id` |
| `turn_start` | The current user turn starts model/tool planning. | `query`, `session_id` |
| `tool_execution_start` | A tool is about to run after guard checks. | `name`, `args`, `session_id` |
| `tool_execution_end` | A tool finished successfully or returned an error payload. | `name`, `result_summary`, `session_id` |
| `message_update` | A visible answer chunk is available. | `content` |
| `agent_end` | Final answer and structured payload are complete. | `answer`, `tools_used`, `tool_result`, `transaction`, `session_id` |
| `agent_error` | The request failed after streaming started. | `message`, `session_id` |

## Legacy Compatibility

The backend still emits:

| Legacy type | Equivalent lifecycle type |
| --- | --- |
| `status` | `agent_start` / `turn_start` |
| `tool` | `tool_execution_end` |
| `chunk` | `message_update` |
| `done` | `agent_end` |
| `error` | `agent_error` |

Frontend migration can be incremental:

1. Add `message_update` as an alias for `chunk`.
2. Add `tool_execution_start` / `tool_execution_end` for richer tool status UI.
3. Switch finalization from `done` to `agent_end`.
4. Keep legacy handlers until all deployed clients are updated.

## Tool Guard Hooks

Every tool call goes through:

1. `before_tool_call`: validates intent, adds idempotency keys, resolves duplicate
   booking/payment flows, and may return a direct answer without executing a tool.
2. tool execution: only whitelisted Python functions in `TOOL_DISPATCH` run.
3. `after_tool_call`: records tool usage, updates search/booking/payment state,
   appends Gemini function-response context, and emits lifecycle metadata.

Payment tools require explicit payment intent. Booking tools use a session-scoped
idempotency key to avoid duplicate reservations for the same restaurant, party,
date, time, and table type.

## Memory Policy

Redis keeps compact turn history for the active session:

- visible `user` and `model` text is kept for recent conversation context;
- transaction payloads are retained so duplicate booking checks still work;
- oversized tool/search payloads are not stored in chat history;
- only the last configured turn window is retained before saving.

This keeps Gemini prompts smaller while preserving the facts needed for booking
continuity.
