# ByteBites Demo Evidence Package

This is the capture checklist for turning ByteBites from a working system into reviewer-visible proof.

Use this document before interviews, portfolio submission, or a recorded walkthrough.

## Evidence Folder

Primary local folders:

```text
output/playwright/full-demo/
output/playwright/flash-deals/
output/playwright/final-demo/
```

These folders contain the current Consumer / LINE / Merchant / AI / Voucher screenshots. The repo does not need to commit new large binary captures unless they are intentionally small and stable.

## Required Evidence

| File | Proof | Pass criteria |
|---|---|---|
| `00-homepage-product-thesis.png` | The product thesis is visible immediately. | Shows ByteBites as AI dining operations, not only restaurant search. |
| `01-ai-recommendation-cards.png` | AI understands a realistic dining request and returns grounded cards. | Shows query, recommendation reasons, and restaurant cards using the same result set. |
| `02-booking-payment-incident.png` | Booking, payment, and real-time incident are real application state, not a static mock. | Shows booking id, paid state, latest open incident, and pending proposal actions. |
| `04-merchant-proposal.png` | Merchant can operate on incidents. | Shows alternative slot proposal or incident resolution controls. |
| `05-line-rescue-card.png` | LINE channel is integrated. | Shows rescue/proposal Flex card with action path. |
| `06-refund-operations-digest.png` | Refund operations are visible. | Shows failed/stale refund summary, digest, or escalation state. |
| `07-ci-portfolio-green.png` | Verification is reviewer-checkable. | Shows GitHub Portfolio CI or terminal output from `scripts/verify-portfolio.sh`. |
| `08-clean-migration-smoke.png` | Fresh-schema startup is protected. | Shows clean MySQL migration smoke workflow or local smoke success. |
| `09-architecture-overview.png` | Architecture is understandable at a glance. | Shows Web, Java, AI, LINE, ETL, Qdrant, data stores, and Nginx boundary. |
| `10-er-model-booking-operations.png` | Core relational model is explainable. | Shows users, shops, booking, incidents, deposit adjustments, refund audit, and merchant notification state. |

Current local captures live under `output/playwright/full-demo/`, `output/playwright/flash-deals/`, and `output/playwright/final-demo/`. LINE evidence now includes real LINE app screenshots plus rendered state proofs. The CI and clean-migration images are rendered evidence cards from `gh run list` and the live migration smoke output. The ER model is documented in `docs/er-model-booking-operations.md`.

## Workbench Evidence Runbook

Use the workbench framing from the merchant UI: start with the blocker, show the state owner, then show the proof artifact.

| Story | Reviewer question | Evidence path | Verification |
|---|---|---|---|
| Consumer booking | Can a user move from AI recommendation to booking/payment/parking? | `output/playwright/full-demo/02-ai-recommendation.png`, `06-booking-no-deposit-success.png`, `07-booking-deposit-paid.png`, `08-parking-reminder-booking.png` | `scripts/demo-readiness.sh --base-url http://localhost:8088 --live-smoke --strict` |
| LINE sync | Is LINE connected to the same booking state as Web? | `output/playwright/full-demo/21-line-booking-hold.png`, `22-line-booking-paid.png`, `23-line-parking-reminder.png`, `27-web-line-linked-booking.png` | `BookingLineNotificationServiceTest`, `BookingSyncContractTest` |
| Merchant workbench | Can merchants see and resolve operational blockers? | `output/playwright/full-demo/10-merchant-overview.png`, `11-merchant-work-queue.png`, `12-merchant-deposit-refund.png`, `18-merchant-rescue-queue.png`, `19-merchant-deposit-delta.png` | `backend-java/src/test/java/com/bytebites/controller/MerchantControllerTest.java` |
| AI quality | Does the AI preserve intent without stale-session bleed? | `ai-service-python/evals/conversation_quality_cases.jsonl`, `ai-service-python/tests/test_agent_conversation_eval.py`, `ai-service-python/tests/test_line_recommendation_fallback.py` | `cd ai-service-python && uv run pytest tests/test_agent_conversation_eval.py tests/test_line_recommendation_fallback.py -q` |
| Voucher seckill | Is the limited voucher path real product logic, not just a badge? | `output/playwright/flash-deals/`, `output/playwright/final-demo/` voucher captures | Redis/Lua/RabbitMQ path tests and merchant voucher summary before AWS release |

For interviews, open these in order. Do not start with implementation details. Start with the workbench question, then show the screenshot, then name the state owner.

## Optional Short Video

Recommended filename:

```text
bytebites-portfolio-walkthrough-3min.mp4
```

Optional GIF preview:

```text
00-bytebites-evidence-walkthrough.gif
```

Use the GIF as a lightweight portfolio-page preview. The recorded walkthrough with personal voiceover remains the primary artifact.

Suggested order:

1. State the thesis: ByteBites is AI dining operations, not just restaurant discovery.
2. Show AI recommendation.
3. Show booking and payment state.
4. Trigger or show late-arrival incident.
5. Show merchant proposal and LINE card.
6. Show refund operations digest.
7. Show architecture and ER model.
8. Close with CI and migration smoke.

Keep it under 5 minutes. The video should prove the workflow, not explain every feature.

The author should record the voiceover personally. See `docs/_internal/portfolio/demo-recording-cloud-plan.md` for the recording and cloud-deployment decision.

Use `docs/_internal/portfolio/demo-recording-script.md` for the exact 3-minute cut, 5-minute walkthrough, and 12-minute interview version.

Use `docs/_internal/portfolio/system-design-interview-pack.md` after the demo when a reviewer asks about architecture tradeoffs, consistency, failure modes, or production rollout boundaries.

Use `docs/performance-query-evidence.md` when a reviewer asks whether the operational flows have indexed query paths or whether performance claims are being overclaimed.

## Live Demo Fallback

If the app is running locally with the Nginx public proxy, use:

```bash
scripts/demo-readiness.sh --base-url http://localhost:8088 --live-smoke --strict
```

For a full local verification pass:

```bash
scripts/release-readiness.sh --full
```

For production-like clean-schema proof:

```bash
scripts/smoke-clean-mysql-migrations.sh --timeout 180
```

## Interview Narrative

Use the same evidence order every time.

5-minute version:

```text
product thesis
  -> AI recommendation
  -> Java-owned booking/payment/incident state
  -> Web/LINE/Merchant coordination
  -> verification and production gaps
```

12-minute version:

```text
product thesis
  -> data pipeline and retrieval
  -> AI orchestration boundaries
  -> booking/payment/incident lifecycle
  -> deposit/refund operations
  -> Nginx deployment boundary
  -> CI, migration smoke, and next production hardening
```

System-design follow-up:

```text
architecture boundary
  -> booking and incident consistency
  -> payment/refund state machines
  -> AI reliability constraints
  -> failure modes
  -> production rollout plan
```

## Production Gap Answer

Do not overclaim production readiness.

Use this concise answer:

```text
The portfolio release is demo-ready and contract-tested.
Production rollout would focus on managed secrets, real PSP refund provider integration,
observability, backups, merchant notification preferences, and cloud deployment.
```
