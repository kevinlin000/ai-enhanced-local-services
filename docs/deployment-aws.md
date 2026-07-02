# AWS Deployment Plan

ByteBites should go to AWS in two stages:

1. Portfolio staging: stable public URL, LINE Login/Bot working, screenshots reproducible.
2. Production-grade hardening: managed data stores, autoscaling, backup drills, alarms, rollback.

The goal is not to invent a second platform. AWS should preserve the route contract already documented in `docs/deployment-nginx.md`.

## Target Public Contract

Keep these public paths stable:

| Public path | Service | Notes |
| --- | --- | --- |
| `/` | Next.js Web | Consumer app, AI chat, merchant console |
| `/api/java/*` | Spring Boot | Strip `/api/java`; includes LINE Login callback |
| `/api/ai/*` | FastAPI AI | AI search, agent, streaming |
| `/api/line/*` | FastAPI AI | LINE Messaging webhook |
| `/line/*` | FastAPI AI | LINE card action pages |
| `/health/java` | Spring Boot | Load balancer health check |
| `/health/ai` | FastAPI AI | Load balancer health check |

LINE settings must point to the AWS HTTPS domain:

```text
LINE Login callback: https://<domain>/api/java/api/auth/line/callback
LINE Messaging webhook: https://<domain>/api/line/webhook
```

## Stage 1: Portfolio Staging

Use this first because it is fast to deploy, easy to debug, and still demonstrates real production thinking.

Recommended shape:

- Route 53 domain, for example `bytebites.<domain>`.
- ACM certificate.
- ALB terminating TLS.
- One EC2 instance in a public subnet for Nginx + app containers.
- RDS MySQL for durable relational data.
- Redis container at first, then ElastiCache Redis when stable.
- RabbitMQ container at first, then Amazon MQ only if the portfolio needs managed queue operations.
- Qdrant container with an attached EBS volume for demo stability.
- CloudWatch logs from Nginx, Java, AI, and worker processes.

Why this is acceptable for portfolio staging:

- It gives a real HTTPS public deployment.
- It keeps cost and operational complexity manageable.
- It exercises LINE OAuth, LINE webhook, Web/Java/AI proxying, Redis, RabbitMQ, Qdrant, MySQL, and Nginx together.
- It remains explainable in an interview.

## Stage 2: Production-Grade Topology

Move to this after the AWS demo is stable:

- ECS Fargate services for Web, Java, AI, voucher worker, and Nginx or ALB path routing.
- RDS MySQL with automated backups, Multi-AZ if needed.
- ElastiCache Redis for cache, session, seckill stock, and idempotency keys.
- Amazon MQ RabbitMQ for durable voucher order events.
- Qdrant on ECS with EBS/EFS, or Qdrant Cloud if operational scope should be reduced.
- CloudWatch alarms for error rate, p95 latency, CPU/memory, Redis memory, RabbitMQ queue depth, RDS storage/connection usage.
- SSM Parameter Store or Secrets Manager for secrets.
- GitHub Actions deployment workflow with manual approval.

## Environment Rules

Production-like AWS should use:

```text
DEMO_MODE_ENABLED=false
SECURITY_STRICT_MODE=true
LINE_AUTH_COOKIE_SECURE=true
LINE_OAUTH_COOKIE_PATH=/api/java/api/auth/line
FRONTEND_URL=https://<domain>
CORS_ALLOWED_ORIGIN_PATTERNS=https://<domain>
LINE_REDIRECT_URI=https://<domain>/api/java/api/auth/line/callback
LINE_PUBLIC_WEB_URL=https://<domain>
```

Secrets must only live in SSM Parameter Store, Secrets Manager, or the deployment host's protected environment. Do not commit `.env` values.

## Data Safety

Before any AWS database migration or seed operation:

1. Take an RDS snapshot or `mysqldump`.
2. Run migration dry-run or staging restore validation where possible.
3. Run `scripts/smoke-clean-mysql-migrations.sh` against a disposable schema.
4. Only then apply migrations to the demo/staging database.

For demo data refreshes, prefer idempotent seed scripts and targeted upserts. Do not run scripts that rebuild or wipe the catalog unless a backup exists and the restore path has been verified.

## Pre-Deploy Checklist

- `scripts/verify-portfolio.sh` passes locally.
- `python3 scripts/verify-ai-portfolio-smoke.py` passes locally with AI service running.
- `scripts/demo-readiness.sh --base-url http://localhost:8088 --live-smoke --strict` passes for the local Nginx route contract.
- LINE Login channel callback URL matches the AWS domain.
- LINE Messaging webhook URL matches the AWS domain.
- RDS snapshot/backup exists.
- Required secrets are present in AWS and not printed in logs.
- Nginx/ALB health checks return healthy for Web, Java, and AI.

## Post-Deploy Smoke

Run these against the AWS domain:

```bash
scripts/demo-readiness.sh --base-url https://<domain> --live-smoke --strict
scripts/smoke-nginx-public-proxy.sh --base-url https://<domain>
AI_BASE_URL=https://<domain> python3 scripts/verify-ai-portfolio-smoke.py
```

Then manually verify:

- LINE Login from browser.
- LINE bot recommendation cards.
- Deposit booking and demo payment.
- Parking reminder card.
- Flash deal claim success and stock decrement.
- Merchant ops pages: work queue, deposit delta, slot capacity, shop list.

## Rollback

Fast rollback for Stage 1:

1. Keep the previous Docker image tags on the EC2 host.
2. Keep the previous Nginx config.
3. If app deploy fails, restart previous containers.
4. If migration fails before write traffic, restore from RDS snapshot or dump.
5. If LINE callback breaks, revert LINE Developers callback URL to the last known working domain and restart Java with matching env.

Do not roll forward under uncertainty for auth, payments, or booking data. Restore first, then investigate.

## What To Screenshot After AWS Is Live

- AWS public Web entry.
- Public AI recommendation with the steak/date/parking smoke query.
- LINE Login callback success on AWS domain.
- LINE bot recommendation cards from AWS domain.
- Booking hold, payment success, parking reminder.
- Flash deal explore/filter/detail/claim/merchant inventory on AWS.
- Merchant ops overview/work queue/deposit delta/slot capacity.
- CloudWatch or deployment dashboard showing healthy services.

## Open Decisions

- Whether Stage 1 Redis remains containerized or moves directly to ElastiCache.
- Whether RabbitMQ remains containerized or moves to Amazon MQ.
- Whether Qdrant is self-hosted on EC2/EBS, ECS/EBS, or Qdrant Cloud.
- Whether Web stays as a Next.js container or moves later to CloudFront/S3 for static portions.
