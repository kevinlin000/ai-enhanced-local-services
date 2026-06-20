# ByteBites Release Boundary

This document defines the current release boundary for portfolio review and formal demo rehearsal. It is intentionally about what is proven, how to verify it, and what not to overclaim.

## Release Thesis

ByteBites is ready to present as an AI dining operations platform:

```text
restaurant discovery
  -> grounded AI recommendation
  -> booking/payment state in Java
  -> conversational reschedule
  -> real-time incident handling
  -> LINE/Web/Merchant coordination
  -> deployment and migration smoke gates
```

The strongest claim is not "the model recommends restaurants." The strongest claim is:

```text
AI can orchestrate the dining workflow, but Java remains the source of truth for booking, payment, incident, and refund state.
```

The portfolio readiness scorecard is maintained at `docs/portfolio-readiness-scorecard.md`. Current recommendation: portfolio-ready at **88 / 100**, demo-ready for interviews, not yet a production SaaS rollout.

## Verification Ladder

Run the checks in this order when preparing a release or presentation.

| Level | Command | Purpose |
|---|---|---|
| Release dry run | `scripts/release-readiness.sh --dry-run` | Print the release checklist without touching services |
| Offline release gate | `scripts/release-readiness.sh --offline` | Fast local contract checks for docs, scripts, workflow, data evidence, and whitespace |
| Full portfolio gate | `scripts/release-readiness.sh --full` | Run Java, AI, ETL, data-quality, deployment contracts, Web tests, and production build |
| Local clean DB smoke | `scripts/smoke-clean-mysql-migrations.sh --timeout 180` | Prove Java/Flyway can boot from a fresh MySQL schema |
| Local public proxy smoke | `scripts/demo-readiness.sh --base-url http://localhost:8088 --live-smoke --strict` | Prove Web/Java/AI/Nginx public routes work together |
| Cloud clean DB smoke | `.github/workflows/clean-mysql-migration-smoke.yml` | Manual GitHub Actions rehearsal with fresh MySQL, Redis, RabbitMQ, and Java |

`scripts/verify-portfolio.sh` intentionally keeps live infra checks as dry-run or workflow-contract checks. Live smoke belongs in formal rehearsal, not every local verification run.

## Release Readiness Script

Use `scripts/release-readiness.sh` as the command router:

```bash
scripts/release-readiness.sh --dry-run
scripts/release-readiness.sh --offline
scripts/release-readiness.sh --full
scripts/release-readiness.sh --live-local --base-url http://localhost:8088
```

Modes:

- `--dry-run`: prints the release checklist.
- `--offline`: runs local contract checks without requiring Web/Java/AI/Nginx live services.
- `--full`: runs `scripts/verify-portfolio.sh`.
- `--live-local`: runs clean MySQL migration smoke and strict public-proxy smoke. Use only after local Docker infra, Web, Java, AI, and Nginx public proxy are running.

## Commit Grouping

The current work should be reviewed or committed in coherent groups:

| Group | Scope |
|---|---|
| Booking operations | booking reschedule, incident handling, proposal lifecycle, deposit adjustment, refund operations |
| AI orchestration | deterministic booking/incident routing, LINE cards, private memory/offers, session state |
| Web operations UI | My Bookings rescue/payment flows, merchant incident/proposal/refund surfaces |
| Deployment boundary | Nginx template, Compose overlay, demo readiness, public-proxy smoke |
| Migration reliability | V16 clean-schema fix, clean MySQL migration smoke, manual GitHub Actions smoke |
| Evidence and docs | README, roadmap, portfolio evidence map, case studies, release boundary |
| Scorecard | portfolio readiness score, role-specific framing, remaining gaps, next plan |

Do not squash these into one anonymous "final update" commit if the goal is reviewer clarity.

## Demo Script

1. Open README and state: ByteBites recommends and arranges.
2. Show `scripts/verify-portfolio.sh` result or CI matrix.
3. Show the Clean MySQL Migration Smoke workflow as the fresh-schema proof.
4. Run or show `scripts/demo-readiness.sh --base-url http://localhost:8088 --live-smoke --strict`.
5. Demo AI recommendation with a concrete dining request.
6. Create or show a booking, payment state, and LINE notification.
7. Ask AI: `我塞車會晚到 20 分鐘`.
8. Show incident state in My Bookings, merchant proposal, LINE proposal card, and accept/decline path.
9. Show private memory or private offer as the personalization layer.
10. Close with the architecture boundary: AI orchestrates; Java owns state.

## Production Gaps

These are intentionally not claimed as complete production systems:

- Real TapPay refund API integration and provider-specific retry semantics.
- Merchant notification preferences and escalation ownership.
- Cloud deployment with managed TLS, secrets, backups, and uptime policy.
- End-to-end browser automation across a fully seeded live demo.
- Full observability dashboards for business incidents and refund operations.
- Real parking-operator reservation integration.

The release is portfolio-grade and demo-ready. It is not yet a production SaaS rollout.
