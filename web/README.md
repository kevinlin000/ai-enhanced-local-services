# ByteBites Web

Next.js frontend for ByteBites. It renders the restaurant discovery page, AI concierge, booking/payment flows, favorites, notifications, and merchant slot management.

## Local Run

Start backend services first:

```bash
cd ~/projects/ai-enhanced-local-services
docker compose up -d
```

Start Java backend:

```bash
cd ~/projects/ai-enhanced-local-services/backend-java
set -a; source .env; set +a
mvn spring-boot:run
```

Start AI service:

```bash
cd ~/projects/ai-enhanced-local-services/ai-service-python
set -a; source .env; set +a
uv run uvicorn app.main:app --reload --port 8000
```

Start web:

```bash
cd ~/projects/ai-enhanced-local-services/web
npm run dev
```

Open http://localhost:3000.

## Environment

Copy `.env.example` to `.env.local`.

For local development, keep browser calls behind Next.js rewrites:

```bash
NEXT_PUBLIC_JAVA_API=/api/java
JAVA_API_PROXY_TARGET=http://localhost:8081
AI_API_PROXY_TARGET=http://localhost:8000
```

For a temporary public demo, deploy the web app and point the proxy targets to public Java/AI URLs, for example ngrok URLs:

```bash
NEXT_PUBLIC_JAVA_API=/api/java
JAVA_API_PROXY_TARGET=https://your-java-url.ngrok-free.app
AI_API_PROXY_TARGET=https://your-ai-url.ngrok-free.app
```

Also add the deployed web origin to Java:

```bash
CORS_ALLOWED_ORIGIN_PATTERNS=https://your-web-demo.example.com,https://*.ngrok-free.app
FRONTEND_URL=https://your-web-demo.example.com
LINE_REDIRECT_URI=https://your-java-url.ngrok-free.app/api/auth/line/callback
```

For a stable public demo or production-like environment, keep ngrok as a local tunnel and put Nginx in front of Web, Java, and AI. Use [Nginx Public Deployment Boundary](../docs/deployment-nginx.md) and keep the browser-facing API paths unchanged:

```bash
NEXT_PUBLIC_JAVA_API=/api/java
LINE_REDIRECT_URI=https://your-domain.example.com/api/java/api/auth/line/callback
LINE_OAUTH_COOKIE_PATH=/api/java/api/auth/line
LINE_PUBLIC_WEB_URL=https://your-domain.example.com
```

For local route rehearsal, run the Nginx Compose overlay and open `http://localhost:8088` after Web, Java, and AI are already running. Then run:

```bash
scripts/demo-readiness.sh --base-url http://localhost:8088
scripts/smoke-nginx-public-proxy.sh --base-url http://localhost:8088
```

## Validation

```bash
npm run test
npm run build
```

Use the main demo path for a presentation:

1. Ask AI for a dining need, such as `大安區 7人 適合聊天`.
2. Open a recommendation card and show review highlights / ABSA detail.
3. Create a booking, choose driving preference, and show deposit payment.
4. Show LINE sync, booking status, cancellation, and parking reminder flow.
