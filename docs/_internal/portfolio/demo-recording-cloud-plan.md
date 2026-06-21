# ByteBites Recording And Cloud Plan

This document answers the practical portfolio question:

```text
Should ByteBites be recorded, deployed to cloud, or hardened like production first?
```

Recommended order:

```text
recorded walkthrough first
  -> optional stable demo cloud
  -> production hardening only after the portfolio evidence is strong
```

## Decision

| Question | Recommendation | Reason |
|---|---|---|
| Should the author record the video personally? | Yes. Record it personally with voiceover. | The interviewer needs to hear engineering judgment: why Java owns state, why AI is deterministic around bookings, and where production boundaries are honest. |
| Should the project be deployed to cloud right now? | Not before the recorded walkthrough. | Cloud helps availability, but it does not automatically make the project easier to understand. A stable recording reduces live-demo risk first. |
| Should production hardening all be completed now? | Not all at once. | Managed secrets, PSP refund provider integration, backups, observability, and operations policy are real production work. For portfolio, document the plan and implement only the highest-signal slice next. |

## Why Recording Comes First

A short recording is the highest-value next artifact because it proves the actual product flow without depending on live services, local tunnels, network conditions, or interview timing.

The recording should show:

1. AI recommendation with grounded cards.
2. Booking and payment state.
3. Real-time incident handling.
4. Merchant proposal and LINE rescue/proposal card.
5. Refund operations digest.
6. Architecture boundary: AI orchestrates; Java owns state.
7. CI / release readiness proof.

Recommended length: 3-5 minutes.

The author should record the narration personally. A silent video or generic screen capture loses the main advantage of the project: the architectural reasoning.

## Cloud Decision

Use three cloud levels, not one vague "deploy it" goal.

| Level | Goal | Needed for portfolio 100? | Notes |
|---|---|---|---|
| Local verified demo | Local app + Nginx public proxy + recorded walkthrough. | Yes. | Current repo already supports this path. |
| Stable portfolio demo cloud | Public URL for Web/Java/AI with managed env vars and demo data. | Useful, not mandatory before recording. | Best after the video, so deployment issues do not block portfolio packaging. |
| Production SaaS cloud | Real customer traffic, managed data stores, backups, observability, secrets, PSP contracts, support process. | No. | This is a separate rollout project, not a portfolio prerequisite. |

## Production Hardening Triage

Do these in order if continuing beyond portfolio packaging.

| Priority | Area | Portfolio expectation | Production expectation |
|---:|---|---|---|
| 1 | Managed secrets | Document required env vars and never commit secrets. | Use a managed secret store, access policy, rotation schedule, and incident process. |
| 2 | Observability | Show health checks, release readiness, and known business metrics. | Dashboards and alerts for incidents, refunds, LINE failures, AI fallback rate, latency, and error budget. |
| 3 | Cloud runtime | Keep Nginx route contract and smoke tests. | Run Web/Java/AI against managed database/cache/queue with TLS, DNS, rollback, and scaling policy. |
| 4 | Backups | Explain backup/restore as a production gap. | Automated backups, restore rehearsal, retention policy, and RPO/RTO targets. |
| 5 | PSP refund provider | Keep demo reconciliation honest. | Real provider refund API, webhook mapping, retry policy, provider error taxonomy, and financial reconciliation. |
| 6 | Operations policy | Show refund SLA/escalation UI. | Merchant preferences, escalation owner, support workflow, and audit retention. |

## What To Say In Interviews

Use this answer when asked why it is not fully production cloud yet:

```text
I treated portfolio readiness and production rollout as separate gates.
The portfolio release is verified by CI, clean-schema migration smoke, Nginx route contracts,
and a recorded walkthrough.
For production, I would next add managed secrets, cloud data stores, backups,
observability, real PSP refund integration, and an operations playbook.
I did not want to overclaim demo-mode integrations as production systems.
```

## Next Work Order

1. Capture the 3-5 minute walkthrough.
2. Capture the evidence screenshots from `docs/_internal/portfolio/demo-evidence-package.md`.
3. Follow the narration and shot order in `docs/_internal/portfolio/demo-recording-script.md`.
4. Store the CI run link and final verification output.
5. Only then choose whether to create a stable public cloud demo.
6. If deploying to cloud, start with a demo environment, not production SaaS.

This order maximizes portfolio score while keeping production claims credible.
