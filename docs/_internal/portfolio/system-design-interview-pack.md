# ByteBites System Design Interview Pack

This pack turns the project into a system-design conversation. It is intentionally about architecture decisions, state ownership, tradeoffs, and failure handling.

Use it after the short demo or when an interviewer asks why the system is designed this way.

## Core Thesis

```text
AI orchestrates the dining workflow.
Java owns booking, payment, incident, and refund state.
```

ByteBites is not presented as a model demo. The model can interpret intent, retrieve restaurants, preserve dialogue context, and render LINE cards. It cannot become the source of truth for bookings, payment obligations, incident resolution, refund reconciliation, or merchant operations.

## 1. Architecture Boundary

| Layer | Responsibility | What It Must Not Own |
|---|---|---|
| Next.js Web | Product surfaces: AI chat, My Bookings, merchant console, public demo UI. | Booking truth, payment settlement, incident state. |
| Spring Boot Java | Transactional business state: booking, payment, incident, proposal, deposit adjustment, refund audit, merchant authorization. | Generated recommendation copy or free-form AI reasoning. |
| FastAPI AI service | Orchestration: intent routing, retrieval, dialogue policy, LINE Flex cards, structured recommendation payloads. | Direct state mutation for booking/payment/refund. |
| ETL pipeline | Data enrichment: crawler, reviews, taxonomy, ABSA, Qdrant payload sync. | Request-time transactional state. |
| Nginx boundary | Stable public route contract for Web, Java, AI, LINE, and health checks. | Business logic. |

Design answer:

```text
I split AI orchestration from Java state because the failure modes are different.
The AI layer can be probabilistic in wording and ranking, but booking/payment/incident state must be deterministic, replayable, and contract-tested.
```

## 2. Booking And Incident Flow

Critical flow:

```text
User says they will be late
  -> AI detects late-arrival intent
  -> Java deterministically finds the recent valid booking
  -> Java creates tb_booking_incident
  -> AI renders LINE rescue/proposal card
  -> Merchant proposes an alternative slot
  -> Customer accepts or declines from Web/LINE
  -> Java validates and mutates booking state
```

Why this matters:

- The model does not guess which booking to modify.
- The incident has explicit `OPEN` / `RESOLVED` state.
- Proposal state supports `PENDING`, `ACCEPTED`, `DECLINED`, and `EXPIRED`.
- Accepted proposals reuse the booking reschedule contract.
- Declined or expired proposals keep the incident operationally visible.

Interview answer:

```text
The late-arrival sentence is natural language, but the state transition is not natural language.
The AI only routes intent. Java creates the incident and owns every follow-up transition.
```

## 3. Consistency Model

The project uses a conservative consistency model for the operational core.

| Concern | Consistency Choice | Reason |
|---|---|---|
| Slot reservation | Reserve new slot before releasing old slot. | A failed reschedule must not destroy the original booking. |
| Paid booking changes | Block automatic changes that create deposit deltas. | Payment obligations must not be silently changed by AI or UI. |
| TOP_UP adjustment | Customer can pay through checkout; Java records settlement. | Payment state stays auditable before merchant applies the booking change. |
| REFUND adjustment | Request and reconcile refund before applying refund-based change. | Provider result may fail or arrive asynchronously. |
| Refund callback | Event-key idempotency and audit trail. | PSP callbacks can be retried or replayed. |
| Refund webhook security | Optional HMAC, current/previous secret rotation, source allowlist. | Demo remains usable, production environments can enforce callback trust. |

Interview answer:

```text
I treated booking mutation and money movement as separate state machines.
That keeps the booking workflow usable while making payment risk explicit instead of hiding it in a reschedule button.
```

## 4. Data Model Defense

The ER model is intentionally scoped to booking operations, not the entire crawler or recommendation schema.

Best diagram:

- `docs/er-model-booking-operations.md`
- `output/playwright/demo-evidence/10-er-model-booking-operations.png`

Key design points:

- `booking_code` is the stable workflow key across Web, LINE, payment, incident, and refund operations.
- `tb_booking_incident` stores the active incident and single pending proposal for the portfolio version.
- `tb_booking_deposit_adjustment` separates booking changes from money movement.
- `tb_booking_refund_reconciliation_event` is append-only audit state for refund callbacks.
- `tb_merchant_shop` is the authorization boundary for merchant APIs.

Tradeoff answer:

```text
For the portfolio version I kept one pending proposal on the incident.
If this became a multi-round negotiation product, I would split proposal history into its own table.
```

## 5. AI Reliability Boundary

The AI layer is reliable only where the product constrains it.

| Risk | Mitigation |
|---|---|
| Model recommends shops that do not match UI cards. | Structured `recommended_shop_ids` drive both narrative and cards. |
| Model guesses a booking. | Booking change and incident routes use deterministic recent-booking lookup. |
| Model ignores private negative memory. | Validator removes shops marked "do not recommend again". |
| Model over-answers vague requests. | Dialogue policy can ask clarification questions. |
| Retrieval returns wrong cuisine/district. | Taxonomy and district constraints guard semantic search. |
| LINE card actions drift from backend state. | LINE actions call Java contracts using action tokens. |

Interview answer:

```text
The reliability work is mostly outside the prompt: structured payloads, validators, deterministic routes, eval cases, and backend contracts.
```

## 6. Failure Modes

| Failure | Expected Behavior |
|---|---|
| New slot is full during reschedule. | Original booking remains unchanged. |
| Customer accepts expired proposal. | Java marks it expired and rejects the state change. |
| Paid booking needs a top-up. | Java creates a TOP_UP adjustment instead of mutating booking immediately. |
| Refund request fails. | Booking change remains blocked; merchant sees failed refund state. |
| Refund callback repeats. | Event key is treated as idempotent replay. |
| Merchant has no LINE binding. | Digest notification returns skipped instead of pretending delivery. |
| Public proxy route drifts. | Nginx verifier and release readiness fail. |
| Fresh schema migration breaks. | Clean MySQL migration smoke catches Flyway startup failure. |

## 7. Verification Story

The verification story is part of the system design.

| Gate | What It Proves |
|---|---|
| `scripts/verify-portfolio.sh` | Java, AI, ETL, data quality, Web tests, Web build, deployment contracts. |
| `.github/workflows/portfolio-ci.yml` | Reviewer-familiar CI matrix for the portfolio gate. |
| `scripts/release-readiness.sh --offline` | Fast release handoff checks without live services. |
| `python3 scripts/verify-performance-query-evidence.py` | Hot query paths, supporting indexes, and operational code anchors still match the documentation. |
| `scripts/smoke-clean-mysql-migrations.sh --timeout 180` | Flyway and Java can boot from a fresh MySQL schema. |
| `scripts/demo-readiness.sh --base-url http://localhost:8088 --live-smoke --strict` | Local public proxy rehearsal across Web, Java, AI, and Nginx. |

Interview answer:

```text
I wanted the repo to be inspectable, not just impressive in a live demo.
That is why the release boundary has offline gates, full portfolio gates, and live rehearsal gates.
```

## 8. Production Rollout Answer

Do not overclaim production SaaS readiness.

Use this answer:

```text
The portfolio release is demo-ready and contract-tested.
For production rollout I would add managed secrets, cloud data stores, backup/restore, observability dashboards, real PSP refund provider integration, merchant notification preferences, and an operations playbook.
```

## 9. Interview Question Bank

| Question | Short Answer |
|---|---|
| Why not let the LLM handle booking changes directly? | Booking/payment changes need deterministic validation, ownership checks, expiry checks, and auditability. |
| Why Java plus Python? | Java owns transactional state; Python is a better fit for AI orchestration, retrieval, evals, and LINE card rendering. |
| Why not put all proposal history in a separate table now? | The portfolio version needs one pending proposal; a separate proposal-history table is the right next step for multi-round negotiation. |
| How do you prevent UI and AI text from diverging? | Structured recommendation ids drive both the narrative and the cards. |
| What happens when a refund fails? | Java blocks the booking change, records audit, exposes SLA/escalation state, and can notify merchant operations. |
| What is the weakest production gap? | Real provider-specific refund integration, managed secrets, cloud operations, observability, and backup policy are still production rollout work. |

## 10. One-Minute Whiteboard Version

```text
Browser and LINE are channels.
Next.js renders product workflows.
FastAPI AI interprets intent, retrieves restaurants, and renders cards.
Spring Boot Java owns booking, payment, incident, proposal, and refund state.
MySQL/Flyway stores the operational truth.
ETL prepares restaurant/review intelligence for Qdrant and MySQL.
Nginx defines the public route boundary.
CI and release gates make the claims replayable.
```
