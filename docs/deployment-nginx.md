# Nginx Public Deployment Boundary

ByteBites should keep two public-entry modes:

| Mode | Use it for | Why |
|---|---|---|
| ngrok | Local, temporary demo tunnels | Fastest way to expose a developer machine to LINE Login and Messaging API |
| Nginx | Stable public demo or production-like deployment | Stable domain, repeatable routing, TLS, proxy headers, health checks, and source allowlist support |

This means Nginx should not delete the ngrok workflow. It should become the stable public entrypoint when the URL must survive a presentation, portfolio review, or production-like environment.

## Route Contract

The template in `deploy/nginx/bytebites.conf.template` keeps the same public paths the Web app already expects:

| Public path | Upstream | Prefix behavior | Purpose |
|---|---|---|---|
| `/` | Next.js Web | Preserve path | App shell, discovery, AI chat, My Bookings, merchant console |
| `/api/java/*` | Spring Boot Java | Strip `/api/java` | Browser-facing Java API, including LINE Login |
| `/api/python/*` | FastAPI AI | Strip `/api/python` | Legacy public smoke path such as `/api/python/health` |
| `/api/ai/*` | FastAPI AI | Preserve `/api/ai` | AI search, agent, and SSE streaming |
| `/api/line/*` | FastAPI AI | Preserve `/api/line` | LINE Messaging API webhook |
| `/line/*` | FastAPI AI | Preserve `/line` | LINE Flex card action pages and lightweight booking pages |
| `/health/java` | Spring Boot Java | Maps to `/actuator/health` | Public Java smoke check |
| `/health/ai` | FastAPI AI | Maps to `/health` | Public AI smoke check |

## Render The Template

Example for one host running all three app processes:

```bash
SERVER_NAME=demo.bytebites.example \
WEB_UPSTREAM=127.0.0.1:3000 \
JAVA_UPSTREAM=127.0.0.1:8081 \
AI_UPSTREAM=127.0.0.1:8000 \
CLIENT_MAX_BODY_SIZE=10m \
envsubst '$SERVER_NAME $WEB_UPSTREAM $JAVA_UPSTREAM $AI_UPSTREAM $CLIENT_MAX_BODY_SIZE' \
  < deploy/nginx/bytebites.conf.template \
  > /etc/nginx/conf.d/bytebites.conf

nginx -t
systemctl reload nginx
```

If the services run in Docker, use container DNS names instead of `127.0.0.1`, for example `WEB_UPSTREAM=bytebites-web:3000`.

## Docker Compose Public Proxy Overlay

For a local rehearsal of the public route contract, start Web, Java, and AI on the host as usual, then run only the Nginx proxy container:

```bash
docker compose \
  -f deploy/docker-compose.yml \
  -f deploy/docker-compose.nginx.yml \
  --profile public-proxy \
  up -d nginx
```

The overlay uses:

```bash
BYTEBITES_PUBLIC_HTTP_PORT=8088
SERVER_NAME=localhost
WEB_UPSTREAM=host.docker.internal:3000
JAVA_UPSTREAM=host.docker.internal:8081
AI_UPSTREAM=host.docker.internal:8000
CLIENT_MAX_BODY_SIZE=10m
```

Open `http://localhost:8088` to exercise the same public paths that a stable domain would expose. Validate the compose merge without starting containers:

```bash
docker compose \
  -f deploy/docker-compose.yml \
  -f deploy/docker-compose.nginx.yml \
  --profile public-proxy \
  config
```

Without `--profile public-proxy`, `docker compose config` intentionally hides the profiled Nginx service.

Stop only the proxy:

```bash
docker compose \
  -f deploy/docker-compose.yml \
  -f deploy/docker-compose.nginx.yml \
  stop nginx
```

For LINE Developers, the public URL still needs HTTPS. Either terminate TLS on the Nginx host, place this proxy behind a TLS load balancer/CDN, or temporarily point ngrok at `localhost:8088` while keeping Nginx as the route contract under test.

## Required Environment

Web:

```bash
NEXT_PUBLIC_JAVA_API=/api/java
JAVA_API_PROXY_TARGET=http://127.0.0.1:8081
AI_API_PROXY_TARGET=http://127.0.0.1:8000
```

Java:

```bash
FRONTEND_URL=https://<domain>
CORS_ALLOWED_ORIGIN_PATTERNS=https://<domain>
LINE_REDIRECT_URI=https://<domain>/api/java/api/auth/line/callback
LINE_OAUTH_COOKIE_PATH=/api/java/api/auth/line
AI_SERVICE_URL=http://127.0.0.1:8000
```

AI service:

```bash
JAVA_BACKEND_URL=http://127.0.0.1:8081
LINE_PUBLIC_WEB_URL=https://<domain>
```

Refund webhook source validation behind Nginx:

```bash
REFUND_WEBHOOK_TRUSTED_PROXIES=127.0.0.1/32
REFUND_WEBHOOK_SOURCE_HEADER=X-Forwarded-For
REFUND_WEBHOOK_ALLOWED_SOURCES=<psp-ip-or-cidr>
```

Use the Nginx host or container subnet in `REFUND_WEBHOOK_TRUSTED_PROXIES` when Nginx is not on `127.0.0.1`.

## LINE Settings

LINE Login callback URL:

```text
https://<domain>/api/java/api/auth/line/callback
```

Messaging API webhook URL:

```text
https://<domain>/api/line/webhook
```

The callback path intentionally includes `/api/java` because the Web app starts LINE Login through `NEXT_PUBLIC_JAVA_API=/api/java`. Java still receives `/api/auth/line/callback` after Nginx strips the public prefix.

## Smoke Checks

Before smoke testing, run the demo readiness preflight:

```bash
scripts/demo-readiness.sh --base-url http://localhost:8088
```

For a stricter local rehearsal that also runs the full public-proxy smoke script:

```bash
scripts/demo-readiness.sh --base-url http://localhost:8088 --live-smoke --strict
```

The preflight does not start or stop services. It checks required deployment files, validates the Compose public-proxy overlay, checks Web/Java/AI/Nginx reachability, and prints start commands when something is missing.

Before a formal rehearsal, also verify that Java can bootstrap from a fresh MySQL schema:

```bash
scripts/smoke-clean-mysql-migrations.sh --timeout 180
```

The clean migration smoke creates a temporary database in the local MySQL container, starts Java on a temporary port, waits for `/actuator/health`, then stops Java and drops the database. It is intentionally separate from `scripts/verify-portfolio.sh` because the live check requires Docker MySQL plus the backend dependencies Java expects, such as Redis and RabbitMQ.

The same check can be run in GitHub Actions through the manual **Clean MySQL Migration Smoke** workflow:

```text
.github/workflows/clean-mysql-migration-smoke.yml
```

That workflow starts Redis and RabbitMQ as services, starts a named MySQL container, then runs:

```bash
scripts/smoke-clean-mysql-migrations.sh --mysql-container bytebites-ci-mysql --timeout 180 --java-port 18081
```

Use this before a high-stakes demo when you want an environment outside your laptop to prove fresh-schema startup.

After Web, Java, AI, and the Nginx public-proxy overlay are running, use the smoke runner:

```bash
scripts/smoke-nginx-public-proxy.sh --base-url http://localhost:8088
```

For a deployed domain:

```bash
scripts/smoke-nginx-public-proxy.sh --base-url https://<domain>
```

The script checks:

- Web root through the public proxy.
- Java health through `/health/java`.
- AI health through `/health/ai`.
- LINE Messaging webhook check through `/api/line/webhook`.
- LINE Login redirect and OAuth state cookie path through `/api/java/api/auth/line/login`.
- AI SSE stream startup through `/api/ai/agent/stream`.

Run a dry run without network calls:

```bash
scripts/smoke-nginx-public-proxy.sh --dry-run
```

Manual fallback:

```bash
curl -i https://<domain>/
curl -i https://<domain>/health/java
curl -i https://<domain>/health/ai
curl -i https://<domain>/api/java/api/auth/line/login
curl -i https://<domain>/api/line/webhook
```

Local compose rehearsal:

```bash
curl -i http://localhost:8088/
curl -i http://localhost:8088/health/java
curl -i http://localhost:8088/health/ai
curl -i http://localhost:8088/api/java/api/auth/line/login
curl -i http://localhost:8088/api/line/webhook
```

For AI streaming, the smoke script checks that `/api/ai/agent/stream` returns `text/event-stream` and emits the initial `agent_start` frame quickly. The Nginx template disables proxy buffering on AI routes so SSE does not silently degrade into delayed responses.
