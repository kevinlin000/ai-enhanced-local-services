# ByteBites Demo Walkthrough

[中文版本](demo-walkthrough.md)

This document is the reviewer-facing walkthrough path for ByteBites. It is not an internal recording checklist and not a feature dump. The goal is to prove one engineering thesis in 3 to 5 minutes:

```text
AI interprets intent and coordinates the workflow.
Java owns booking, payment, incident, and refund state.
```

The demo is not about showing that the model can chat. It is about showing how an AI product can operate around transactional state while keeping state ownership, data quality, and verification clear.

## 3-Minute Version

| Time | Screen | What It Proves |
|---:|---|---|
| 0:00-0:20 | README or homepage | ByteBites is an AI dining operations platform, not a one-shot restaurant chatbot. |
| 0:20-0:55 | AI recommendation cards | AI handles ambiguous dining intent, but the UI uses structured recommended shop ids so text and cards do not drift apart. |
| 0:55-1:25 | My Bookings | Once the user books, Java becomes the source of truth for booking, payment, rescheduling, and deposit state. |
| 1:25-2:05 | Incident and merchant proposal | Late arrival creates a deterministic Java incident from the latest valid booking; the merchant can propose an alternative slot. |
| 2:05-2:30 | LINE Flex card | LINE is an action channel, not the state owner; accept and decline still call Java transactions. |
| 2:30-3:00 | Architecture / CI | Close with the boundary: AI orchestrates, Java owns state, and CI / release gates verify the claims. |

## 5-Minute Version

| Time | Screen | Narrative |
|---:|---|---|
| 0:00-0:25 | README / homepage | State the product thesis: recommendation is only the entry point; the engineering value is booking, payment state, incidents, LINE coordination, and operations. |
| 0:25-1:00 | AI chat / recommendation cards | Show natural-language search, recommendation reasons, photos, and cards. The key point is that text and cards share structured shop ids. |
| 1:00-1:35 | Booking / demo payment | Show booking code, payment state, party size, and time. Transaction state is not stored by the model. |
| 1:35-2:20 | Real-time incident handling | Use the late-arrival flow to show that AI does not guess the booking; Java creates `tb_booking_incident` from the latest valid booking. |
| 2:20-3:00 | Merchant console | Show OPEN incident, alternative slot proposal, and PENDING / ACCEPTED / DECLINED / EXPIRED lifecycle. |
| 3:00-3:30 | LINE card | Explain that the Flex card only gives the customer an action path; Java validates identity, expiry, slot, and deposit policy. |
| 3:30-4:05 | Refund operations | Show refund operations digest, FAILED / stale PROCESSING visibility, and escalation notes. Be explicit that demo reconciliation is not a real PSP rollout. |
| 4:05-4:35 | Architecture / ER model | Use architecture and ER docs to explain Web, AI, Java, LINE, ETL, Qdrant, MySQL, and Nginx boundaries. |
| 4:35-5:00 | CI / release readiness | Show `scripts/verify-portfolio.sh`, Portfolio CI, release readiness, and clean migration smoke. |

## Short Voiceover Script

```text
This is ByteBites. I built it as an AI dining operations platform, not just a restaurant recommendation chatbot.

The first part is discovery. A user can describe a dining need in natural language. The AI service interprets district, cuisine, party size, occasion, and preferences. But when it returns to the product surface, it uses structured recommended shop ids, so the narrative and recommendation cards stay aligned.

The second part is booking. Once the user moves into booking, Java becomes the source of truth. Booking code, date, time, party size, payment state, rescheduling, and deposit adjustments are owned by Java contracts, not by model memory.

The third part is real-time incident handling. If the customer says they will be 20 minutes late, the system does not let the model guess which booking to update. It deterministically finds the latest valid booking and creates an incident in Java. The merchant can then propose an alternative slot, and the customer can accept or decline.

The fourth part is LINE. LINE is an action channel, not a state source. A Flex card can notify the customer, but accept and decline still call back into Java transactions that validate identity, expiry, booking rules, and deposit policy.

The fifth part is operations. The project also covers top-up, refund reconciliation, failed refunds, SLA visibility, escalation notes, and refund operations digest. I do not present the demo callback as a real PSP rollout; production would integrate a real refund provider separately.

The architecture boundary is the main point: Next.js is the product surface, FastAPI AI service orchestrates and renders LINE cards, Java Spring Boot owns booking/payment/incident/refund state, ETL prepares restaurant and review data for MySQL and Qdrant, and Nginx defines the public route boundary.

I would call this portfolio-ready: it is implemented as vertical slices and protected by CI, release readiness, clean MySQL migration smoke, and tests. I would not call it production SaaS yet. Production rollout would need managed secrets, cloud runtime, backups, observability, a real PSP refund provider, and operations policy.
```

## Evidence Map

| Claim | Demo Screen | Evidence |
|---|---|---|
| Not a chatbot-only demo | AI recommendation -> booking -> incident -> refund operations | [Architecture Overview](architecture-overview.md) |
| Java owns transaction state | My Bookings, merchant console, incident proposal | [Booking Operations ER Model](er-model-booking-operations.md) |
| AI has reliability boundaries | Late-arrival prompt, structured recommendation ids, evals | [AI Dialogue State Case Study](case-studies/10-ai-dialogue-state.md) |
| Data quality is reviewable | Data coverage, taxonomy, ABSA, Qdrant payloads | [Data Coverage Report](data-coverage-report.md) |
| Deployment and verification are part of the work | Portfolio CI, Nginx contract, migration smoke | [Public Deployment Rehearsal](case-studies/11-demo-deployment.md) |
| Performance claims are bounded | Hot query paths, indexes, code anchors | [Performance And Query Evidence](performance-query-evidence.md) |

## Before Recording

At minimum:

```bash
scripts/release-readiness.sh --offline
scripts/verify-portfolio.sh
```

If the local services and Nginx public proxy are running:

```bash
scripts/demo-readiness.sh --base-url http://localhost:8088 --live-smoke --strict
```

Clean database startup proof:

```bash
scripts/smoke-clean-mysql-migrations.sh --timeout 180
```

## Do Not Overclaim

This project is portfolio-ready, contract-tested, and demo-ready. It should not be presented as production SaaS.

Production rollout still needs managed secrets, cloud runtime and data stores, backup and restore policy, observability dashboards and alerting, a real PSP refund provider, merchant notification preferences, and an operations runbook.
