# ByteBites Portfolio Evidence Map

> Purpose: give reviewers a fast route from portfolio claims to code, tests, data evidence, and demo flows. This is the document to open when applying for Java backend, AI application, or full-stack roles.

## 1. One-Screen Positioning

ByteBites is an **AI dining operations platform**. It does not stop at restaurant discovery. It connects:

```text
natural-language dining need
  -> grounded restaurant recommendation
  -> booking draft
  -> Java booking state
  -> demo deposit payment
  -> conversational booking change
  -> real-time incident handling
  -> private dining memory
  -> private AI-matched offer
  -> LINE notification / cancellation / waitlist
  -> parking reminder
```

The strongest interview framing is:

```text
Data quality -> AI reliability -> transaction consistency -> product differentiation
```

## 2. Reviewer Entry Points

| Question | Best Evidence |
|---|---|
| Is this only a chatbot demo? | `docs/case-studies/07-web-line-booking-sync.md`, `backend-java/src/main/java/com/bytebites/controller/BookingController.java`, `scripts/verify-portfolio.sh` |
| Is the Java backend doing real business work? | `BookingSlotInventory`, `BookingRescheduleService`, `BookingDepositAdjustmentService`, `BookingPayloadMapper`, payment/cancel/reschedule/availability/deposit-policy tests |
| Is the AI reliable or only fluent? | `ai-service-python/evals/`, `ai-service-python/tests/test_agent_conversation_eval.py`, `docs/case-studies/10-ai-dialogue-state.md` |
| Does the AI actually remember user preferences? | `DiningMemoryService`, `web/app/my-bookings/page.tsx`, private-memory tests in `test_line_recommendation_fallback.py` |
| Are offers real product logic or just UI labels? | `PrivateAiOfferService`, `V43__private_ai_offers.sql`, private-offer tests in Java and AI |
| Can the system handle live booking issues? | `BookingIncidentService`, `MerchantController`, `BookingRescheduleService`, `BookingDepositAdjustmentService`, `PaymentController`, `V44__booking_incidents.sql`, `V45__booking_incident_proposals.sql`, `V46__booking_incident_proposal_expiry.sql`, `V47__booking_deposit_adjustments.sql`, `V48__booking_deposit_adjustment_settlement.sql`, `V49__booking_refund_reconciliation_audit.sql`, `V50__booking_refund_escalation.sql`, `V51__merchant_notification_dispatch.sql`, `internal_line_booking_incident`, `internal_line_booking_incident_proposal`, `internal_line_refund_operations_digest`, My Bookings rescue UI, merchant incident queue, slot suggestions, proposal accept/decline/expiry, paid-booking deposit delta guard, merchant manual adjustment queue, PSP settlement tracking, refund reconciliation idempotency/audit/signature verification/rotation/source allowlist, refund SLA visibility/escalation/operations digest notification/scheduled policy |
| Is the data real enough for recommendation? | `docs/data-coverage-report.md`, `scripts/verify-data-quality.py`, `docs/case-studies/06-data-crawler-coverage.md` |
| Is Web and LINE state consistent? | `BookingSyncContractTest`, `BookingLineNotificationServiceTest`, `docs/case-studies/07-web-line-booking-sync.md` |
| Is the frontend production-minded? | `web/tests/`, `web/package.json`, `docs/case-studies/12-premium-ui-positioning.md` |
| Can the public demo move beyond a temporary tunnel? | `docs/deployment-nginx.md`, `docs/_internal/portfolio/release-boundary.md`, `deploy/nginx/bytebites.conf.template`, `deploy/docker-compose.nginx.yml`, `scripts/demo-readiness.sh`, `scripts/smoke-nginx-public-proxy.sh`, `scripts/smoke-clean-mysql-migrations.sh`, `.github/workflows/clean-mysql-migration-smoke.yml`, `scripts/verify-nginx-template.py`, `docs/case-studies/11-demo-deployment.md` |
| Can the design stand up to system-design questions? | `docs/_internal/portfolio/system-design-interview-pack.md`, `docs/architecture-overview.md`, `docs/er-model-booking-operations.md`, `docs/_internal/portfolio/demo-evidence-package.md` |
| Are hot operational queries indexed and explainable? | `docs/performance-query-evidence.md`, `scripts/verify-performance-query-evidence.py`, booking/incident/deposit/refund migrations |
| Can a reviewer verify the repo quickly? | `docs/_internal/portfolio/release-boundary.md`, `scripts/release-readiness.sh`, `scripts/verify-portfolio.sh`, `.github/workflows/portfolio-ci.yml`, `.github/workflows/clean-mysql-migration-smoke.yml` |

## 3. Java Backend Track

Use this track when applying for Java backend roles.

### What to emphasize

- Java owns booking, payment, cancellation, availability, parking reminders, and persisted user state.
- Booking capacity is not front-end mock state. It is guarded by a dedicated inventory Module.
- Rescheduling is transactional: reserve the new slot, then release the old slot, and leave the original booking untouched if the new slot is full.
- Private dining memory is persisted in Java and tied to booking ownership, not stored only in prompts.
- Private AI-matched offers are persisted separately from public vouchers and guarded by per-user/per-shop reuse.
- Booking incidents are persisted in Java and pushed through the same LINE internal notification path as booking/payment events.
- Web and LINE are entry points into the same backend booking state.
- Demo payment still writes backend transaction state and notification payloads.

### Code anchors

| Claim | Code / Test |
|---|---|
| Atomic booking capacity | `backend-java/src/main/java/com/bytebites/service/BookingSlotInventory.java` |
| Transactional booking changes | `backend-java/src/main/java/com/bytebites/service/BookingRescheduleService.java` |
| Private preference memory | `backend-java/src/main/java/com/bytebites/service/DiningMemoryService.java`, `backend-java/src/test/java/com/bytebites/service/DiningMemoryServiceTest.java` |
| Private AI-matched offers | `backend-java/src/main/java/com/bytebites/service/PrivateAiOfferService.java`, `backend-java/src/test/java/com/bytebites/service/PrivateAiOfferServiceTest.java`, `backend-java/src/main/resources/db/migration/V43__private_ai_offers.sql` |
| Real-time booking incidents | `backend-java/src/main/java/com/bytebites/service/BookingIncidentService.java`, `backend-java/src/test/java/com/bytebites/service/BookingIncidentServiceTest.java`, `backend-java/src/main/resources/db/migration/V44__booking_incidents.sql` |
| Booking payload contract shared by controller and LINE notification | `backend-java/src/main/java/com/bytebites/service/BookingPayloadMapper.java` |
| Web payment/cancel/reschedule sync | `backend-java/src/test/java/com/bytebites/controller/BookingSyncContractTest.java` |
| LINE notification payload | `backend-java/src/test/java/com/bytebites/service/BookingLineNotificationServiceTest.java` |
| Availability release and notification | `backend-java/src/test/java/com/bytebites/service/AvailabilityNotificationSyncContractTest.java` |
| Parking reminder behavior | `backend-java/src/test/java/com/bytebites/service/ParkingReminderServiceTest.java` |

### Interview sentence

```text
I kept Java as the source of truth for transactional behavior. The AI layer can recommend and orchestrate, but booking/payment/cancel state is verified through Java contracts.
```

## 4. AI Application Track

Use this track when applying for AI application engineer roles.

### What to emphasize

- The AI agent is not a one-shot prompt. It has routing, retrieval, constraints, conversation state, booking drafts, and regression tests.
- Conversational booking changes are routed deterministically from the latest valid booking, not guessed by the model.
- Late-arrival rescue messages are routed deterministically from the latest valid booking, not guessed by the model.
- Private "do not recommend again" signals are enforced by a validator, not only prompt wording.
- Private AI-matched offers are fetched from Java during recommendation enrichment only when intent matches discount/off-peak/save-money signals.
- Qdrant semantic hits are constrained by taxonomy, district, cuisine, and dining context.
- The same recommendation payload drives text, cards, booking CTA, and final agent response.
- Vague needs are clarified instead of hallucinated into recommendations.

### Code anchors

| Claim | Code / Test |
|---|---|
| Booking draft state | `ai-service-python/app/booking_draft.py`, `ai-service-python/tests/test_booking_draft.py` |
| Conversational reschedule route | `ai-service-python/app/main.py`, `ai-service-python/tests/test_line_recommendation_fallback.py` |
| Incident routing and LINE rescue/proposal cards | `ai-service-python/app/main.py`, `test_web_agent_stream_creates_booking_incident_for_late_arrival`, `test_internal_booking_incident_pushes_line_card`, `test_internal_booking_incident_proposal_pushes_line_card` |
| Private memory recommendation guard | `ai-service-python/app/main.py`, `test_private_memory_validator_removes_avoided_recommendation` |
| Private offer recommendation signal | `ai-service-python/app/main.py`, `test_private_ai_offer_annotation_is_in_compact_context`, `test_enrich_agent_search_result_attaches_private_ai_offers` |
| Conversation memory fallback | `ai-service-python/app/session_store.py`, `ai-service-python/tests/test_session_store.py` |
| Agent dialogue regression cases | `ai-service-python/tests/test_agent_conversation_eval.py` |
| LINE recommendation fallback | `ai-service-python/tests/test_line_recommendation_fallback.py` |
| Eval manifests | `ai-service-python/evals/conversation_quality_cases.jsonl`, `ai-service-python/evals/agent_concierge_cases.jsonl` |
| Agent event contract | `docs/ai-agent-event-contract.md` |

### Quality Gates To Mention

The AI quality story is now reviewer-checkable:

```text
fresh user intent
  -> no stale session merge unless the new turn is a clarification
  -> semantic search only when needed
  -> deterministic booking draft edits
  -> validator rejects cuisine/price/category drift
  -> manifest cases require executable gates
```

Use `ai-service-python/evals/conversation_quality_cases.jsonl` to show the product bar, then `ai-service-python/tests/test_agent_conversation_eval.py` to show it is executable.

### Interview sentence

```text
The hardest part was not calling an LLM. It was deciding when to search, when to clarify, when to preserve a draft, and when to refuse unsafe automation.
```

## 5. Full-Stack Track

Use this track when applying for full-stack roles.

### What to emphasize

- The frontend is not detached from backend state. Booking, payment, notifications, and AI cards are contract-driven.
- The "My bookings" page can pay, reschedule, cancel, and reload the backend source of truth.
- The "My bookings" page can create rescue incidents and show the latest open incident from backend state.
- The merchant page can read open incidents for owned shops and resolve them without using customer booking permissions.
- Java computes same-day alternative slot suggestions from slot inventory; the merchant page only displays backend suggestions.
- Merchants can send one pending alternative-time proposal; customers accept or decline from My Bookings or LINE, expired proposals are blocked by Java, and accepted proposals run the existing reschedule contract.
- Paid bookings cannot be automatically rescheduled into a deposit top-up or refund state; Java blocks the change before slot capacity is mutated.
- Blocked paid-booking deposit deltas create adjustment tasks; TOP_UP can be paid from My Bookings through TapPay checkout, REFUND must move through request/reconciliation success or failure, refund callbacks are idempotent by event key, optional HMAC verification protects configured webhook environments with current/previous secret rotation and source allowlist, stuck or failed refunds are surfaced in merchant SLA visibility and an operations digest, can be pushed as a LINE digest to linked merchant accounts, can be evaluated by scheduler-ready cooldown policy with dispatch audit, can be marked escalated with audit, and Java requires PSP settlement status, provider, transaction id, amount, and completion time before applying the reschedule.
- Users can record private post-meal tags from My Bookings; the UI shows the saved memory without creating a public review feed.
- AI recommendation cards can show a private offer badge only when the backend returns a matched offer; no public coupon page is added.
- Web AI and LINE bot are two channels over the same product workflow.
- UI contract tests protect product decisions: no heavy marketing hero, consistent AI card payloads, restrained workspace surfaces.

### Code anchors

| Claim | Code / Test |
|---|---|
| Web contract tests | `web/tests/*.test.mjs` |
| Booking management UI | `web/app/my-bookings/page.tsx`, `web/lib/api.ts` |
| Rescue incident UI | `web/app/my-bookings/page.tsx`, `web/lib/api.ts` |
| Merchant incident console and slot suggestions | `web/app/merchant/page.tsx`, `backend-java/src/main/java/com/bytebites/controller/MerchantController.java`, `backend-java/src/test/java/com/bytebites/controller/MerchantControllerTest.java` |
| Customer proposal lifecycle | `web/app/my-bookings/page.tsx`, `ai-service-python/app/main.py`, `backend-java/src/main/java/com/bytebites/controller/BookingController.java`, `backend-java/src/test/java/com/bytebites/controller/BookingSyncContractTest.java`, `ai-service-python/tests/test_line_recommendation_fallback.py` |
| Paid-booking deposit delta guard, customer TOP_UP checkout, REFUND reconciliation, and refund SLA/escalation report | `backend-java/src/main/java/com/bytebites/service/BookingRescheduleService.java`, `backend-java/src/main/java/com/bytebites/service/BookingDepositAdjustmentService.java`, `backend-java/src/main/java/com/bytebites/controller/PaymentController.java`, `backend-java/src/main/java/com/bytebites/controller/MerchantController.java`, `backend-java/src/main/resources/db/migration/V47__booking_deposit_adjustments.sql`, `backend-java/src/main/resources/db/migration/V48__booking_deposit_adjustment_settlement.sql`, `backend-java/src/main/resources/db/migration/V49__booking_refund_reconciliation_audit.sql`, `backend-java/src/main/resources/db/migration/V50__booking_refund_escalation.sql`, `backend-java/src/test/java/com/bytebites/controller/BookingSyncContractTest.java`, `backend-java/src/test/java/com/bytebites/controller/PaymentSyncContractTest.java`, `backend-java/src/test/java/com/bytebites/controller/MerchantControllerTest.java`, `backend-java/src/test/java/com/bytebites/service/BookingDepositAdjustmentServiceTest.java`, `web/app/my-bookings/page.tsx`, `web/app/merchant/page.tsx` |
| Private post-meal tags | `web/app/my-bookings/page.tsx`, `web/lib/api.ts` |
| AI private offer display | `web/components/AgentShopCard.tsx`, `web/lib/agentTypes.ts`, `web/lib/api.ts` |
| AI final payload contract | `web/tests/agent-final-payload.test.mjs` |
| App shell and design guards | `web/tests/app-shell.test.mjs`, `web/tests/design-contract.test.mjs` |
| Offline-friendly production build | `web/package.json` `build:ci` |
| Web/LINE booking story | `docs/case-studies/07-web-line-booking-sync.md` |
| Premium product positioning | `docs/case-studies/12-premium-ui-positioning.md` |

### Interview sentence

```text
I treated UI, AI text, cards, booking state, and LINE notifications as one product contract instead of separate demos.
```

## 6. Verification Checklist

Run the full portfolio gate before sharing the repository:

```bash
scripts/verify-portfolio.sh
```

Expected coverage:

| Area | What It Proves |
|---|---|
| Java tests | booking/payment/reschedule/private-memory/LINE/parking business contracts |
| AI tests | dialogue state, guardrails, LINE behavior, session fallback |
| ETL tests | taxonomy and data pipeline assumptions |
| Data quality gate | 600-shop coverage, eval manifests, taxonomy decisions, case-study links |
| Deployment and release gates | Stable public reverse-proxy route contract, Docker Compose public-proxy overlay, demo-readiness and public-proxy smoke-runner syntax/dry-run, clean MySQL migration smoke-runner syntax/dry-run, manual GitHub Actions clean-schema smoke workflow contract, release-readiness handoff contract, LINE callback/webhook URLs, proxy headers, and refund source allowlist guidance |
| Markdown link check | reviewer-facing documentation does not silently drift into broken links |
| Web tests | UI contract and AI payload contract |
| Web build | production compilation without external font fetch |

CI mirror:

```text
.github/workflows/portfolio-ci.yml
.github/workflows/clean-mysql-migration-smoke.yml
docs/_internal/portfolio/release-boundary.md
scripts/release-readiness.sh
```

## 7. Demo Script For Reviewers

1. Open README and state the thesis: **會推薦，也會安排**.
2. Run `scripts/verify-portfolio.sh` or show CI.
3. Show AI query: `推薦大安區美式漢堡`.
4. Show vague query: `推薦7人聚餐餐廳`.
5. Show follow-up booking: `明天晚上 7 點 4 人`.
6. Show Java booking/payment state and LINE notification.
7. Ask AI: `改成明晚 8 點，同樣 4 位`, then show the updated My Bookings state.
8. Ask AI: `我塞車會晚到 20 分鐘`, then show the rescue incident, LINE card, merchant slot proposal, LINE proposal card, and My Bookings accept/decline path.
9. Record `太吵` / `不再推薦` in My Bookings, then show AI recommendation avoids that shop.
10. Ask AI: `想找有優惠、比較省錢的日式料理`, then show the private offer badge on the recommendation card.
11. Close with the evidence chain: data quality, AI state, backend contract, Web/LINE consistency.

## 8. What Not To Overclaim

- Demo payment proves transaction state, top-up checkout, refund reconciliation state/idempotency/signature rotation/source allowlist boundary, refund SLA escalation report, triggerable refund operations LINE digest, scheduler-ready cooldown policy, and notification flow; it is not a production payment settlement system.
- Parking reservation is a product-direction demo, not a live parking-operator integration.
- Private AI offers prove matching logic and private display; production merchant settlement and fraud controls would need deeper quota, checkout, and analytics work.
- Incident handling proves workflow coordination; production would still need provider-specific refund operations and merchant notification preferences.
- AI recommendation is advisory; the system improves reliability through constraints, state, and tests, not by claiming perfect judgment.
- Public demo mode is presentation-friendly; production hardening should tighten secrets, internal endpoints, and environment policy.
- ngrok is a local temporary tunnel, not the long-term deployment architecture; stable public demos should use the documented Nginx route contract, the Compose public-proxy overlay, or an equivalent managed reverse proxy.
