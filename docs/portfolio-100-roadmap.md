# ByteBites Portfolio 100 Roadmap

This document defines what "100 / 100" means for ByteBites.

The goal is not to pretend every production concern is solved. The goal is to make the project score as highly as possible under a clear portfolio-review rubric, while keeping production rollout gaps honest.

## Two Different 100s

| Target | Meaning | Can be reached in this repo now? |
|---|---|---|
| Portfolio 100 | A reviewer can understand the product, inspect the architecture, replay the demo path, and verify the engineering claims without guesswork. | Yes. |
| Production SaaS 100 | Real merchant onboarding, managed cloud infrastructure, real PSP refund integration, secrets, backups, uptime, observability, and operational ownership are complete. | No. Requires external providers and deployment work. |

The current scorecard stays at `88 / 100` until the evidence package is filled with actual screenshots, video, and the final demo checklist result.

## Portfolio 100 Rubric

| Area | Current | 100-point requirement |
|---|---:|---|
| Product story | Strong | One short narrative explains why ByteBites is AI dining operations, not a chatbot. |
| Architecture | Strong but distributed | One diagram shows state ownership and channel boundaries at a glance. |
| Demo evidence | Scattered | A reviewer-facing evidence package contains the exact screenshots, video, CI proof, and fallback commands. |
| Verification | Strong | Local verifier, CI matrix, release readiness, clean migration smoke, and public-proxy smoke are linked from one place. |
| Production-gap answer | Honest but broad | A concise answer separates demo-grade proof from production rollout work. |
| Interview delivery | Not packaged | 5-minute and 12-minute walkthroughs use the same evidence order. |

## Path To Portfolio 100

1. Create the architecture overview.
   - Required artifact: `docs/architecture-overview.md`.
   - Acceptance: one diagram explains Web, Java, AI, LINE, ETL, Qdrant, MySQL, Redis/RabbitMQ, and Nginx public boundary.

2. Create the demo evidence package.
   - Required artifact: `docs/demo-evidence-package.md`.
   - Acceptance: every screenshot/video/CI proof item has a filename, purpose, and pass criteria.

3. Decide the recording and cloud order.
   - Required artifact: `docs/demo-recording-cloud-plan.md`.
   - Acceptance: the project has a clear answer for personal voiceover, stable demo cloud, and production hardening scope.

4. Record or capture the evidence.
   - Required artifacts: screenshots, a 3-5 minute video, and CI run links.
   - Acceptance: the evidence package can be reviewed without running the app live.

5. Prepare interview scripts.
   - Required artifact: `docs/demo-recording-script.md`.
   - Acceptance: both scripts reinforce the same thesis: AI orchestrates; Java owns state.

6. Run final verification.
   - Required command: `scripts/release-readiness.sh --full`.
   - Optional rehearsal: `scripts/release-readiness.sh --live-local --base-url http://localhost:8088`.
   - Acceptance: local full verification and GitHub Portfolio CI are green.

## Production 100 Roadmap

These are not blockers for portfolio 100, but they are the correct next answer if asked what production rollout would require.

| Area | Production work |
|---|---|
| Payment/refund | Replace demo reconciliation with provider-specific TapPay refund APIs, webhook events, retry semantics, and provider error taxonomy. |
| Security/secrets | Managed secrets, key rotation process, least-privilege service credentials, audit log retention, and callback source policy per environment. |
| Cloud runtime | Managed TLS, DNS, cloud database, Redis/RabbitMQ equivalents, backup/restore policy, and deployment rollback. |
| Observability | Business dashboards for booking incidents, refund SLA, AI fallback rate, LINE push failures, and public route health. |
| Operations | Merchant notification preferences, escalation ownership, support playbooks, and incident response policy. |
| Browser coverage | End-to-end browser tests against a seeded demo environment for AI-to-booking-to-LINE flows. |

## Next Score Lift

The fastest way to raise the score is not another product feature.

The next score lift is evidence packaging:

```text
architecture overview
  -> demo evidence package
  -> recording and cloud plan
  -> screenshots/video
  -> final verification result
  -> interview walkthrough
```

When those are complete, the portfolio score can reasonably move from `88 / 100` toward `95-100 / 100` for interview use.
