# Case Study 11: 公開展示部署 — 從本機可跑到外部可開

**TL;DR** 公開展示前，最大的風險不是功能少，而是外部環境打不開。ByteBites 需要 Web、Java、AI、RabbitMQ、Qdrant、LINE Login、LINE bot、CORS、callback URL、ngrok public URL 全部對齊。這篇記錄如何把本機系統整理成可展示的公開入口。

**Tech:** Next.js rewrites / Spring Boot config / ngrok / Nginx boundary / Docker Compose / LINE Developers / health checks
**Repo:** `web/README.md`, `docs/deployment-nginx.md`, `deploy/nginx/bytebites.conf.template`, `deploy/docker-compose.nginx.yml`, `scripts/demo-readiness.sh`, `scripts/smoke-nginx-public-proxy.sh`, `scripts/smoke-clean-mysql-migrations.sh`, `.github/workflows/clean-mysql-migration-smoke.yml`, `docker-compose.yml`, `backend-java/src/main/resources/application.yaml`

## 1. 問題：本機能跑，不代表外部使用者能看

本機開 `localhost:3000` 很容易，但外部使用者需要公開 HTTPS URL。LINE Login 和 Messaging API 也需要公開 callback/webhook。

這牽涉：

- Web public URL。
- Java backend callback URL。
- AI service webhook URL。
- CORS allowed origins。
- LINE Login channel callback。
- Messaging API webhook。
- cookie path。
- ngrok warning page。
- Docker Compose project naming。

## 2. 第一個坑：Web proxy 下的 LINE OAuth cookie path

Java 原本 auth path 是：

```text
/api/auth/line/login
/api/auth/line/callback
```

但公開 demo 透過 Next.js proxy：

```text
/api/java/api/auth/line/login
/api/java/api/auth/line/callback
```

如果 state cookie path 仍是 `/api/auth/line`，瀏覽器回 callback 時不會帶 cookie，LINE OAuth state validation 會失敗。

修法：把 cookie path 變成可配置：

```yaml
line:
  oauth:
    cookie-path: ${LINE_OAUTH_COOKIE_PATH:/api/auth/line}
```

demo 環境設成：

```text
LINE_OAUTH_COOKIE_PATH=/api/java/api/auth/line
```

## 3. 第二個坑：LINE channel 權限與 Published 狀態

LINE Developers 有兩種 channel：

- Messaging API：聊天 bot。
- LINE Login：Web 登入。

一開始容易把 callback URL 找錯地方，或使用只有 Tester 權限的舊 channel。最後建立新的 LINE Login channel，發布 Published，更新 Java env 的 `LINE_CHANNEL_ID` / `LINE_CHANNEL_SECRET`，並驗證 redirect：

```text
client_id=2010368383
redirect_uri=https://.../api/java/api/auth/line/callback
```

這一步很重要：如果 channel 還在 Developing，外部使用者不一定能登入。

## 4. 第三個坑：Docker Compose project name

專案裡有 root compose 和 deploy compose。固定 `container_name` 在不同 compose project 下容易撞名。

修法：root `docker-compose.yml` 明確指定：

```yaml
name: deploy
```

讓 `docker compose up -d` 能接上既有 RabbitMQ、Qdrant、Prometheus、Grafana，而不是建立另一組同名 container。

## 5. Smoke tests

部署不是口頭說明，要用 endpoint 驗證：

```text
GET /                         -> 200
GET /api/python/health         -> {"status":"ok"}
GET /api/java/actuator/health  -> {"status":"UP"}
GET /api/java/api/auth/line/login -> 302 to LINE authorize
```

LINE Login redirect 還要檢查：

- `client_id` 是新的 LINE Login channel。
- `redirect_uri` 是公開 HTTPS callback。
- `Set-Cookie Path` 是 proxy 後的 path。

## 6. 後續邊界：ngrok vs Nginx

ngrok 適合本機臨時 demo，因為它能最快把 `localhost:3000` 暴露成 LINE 可呼叫的 HTTPS URL。但它不是穩定公開部署策略：URL 生命週期、proxy headers、TLS、health checks、refund webhook source allowlist，都需要更明確的邊界。

因此後續補上 Nginx public deployment boundary，而不是把 ngrok 流程刪掉：

```text
ngrok -> local temporary tunnel
Nginx -> stable public reverse proxy
```

Nginx route contract 保留既有 public paths：

```text
/api/java/*   -> Java, strip /api/java
/api/ai/*     -> AI, preserve /api/ai
/api/line/*   -> AI LINE webhook
/line/*       -> AI LINE action pages
```

這讓 Web、LINE Login、Messaging API webhook 和 AI streaming 不需要換一套 URL 規則。最重要的是，LINE Login callback 仍維持：

```text
https://<domain>/api/java/api/auth/line/callback
```

Java 仍實際收到 `/api/auth/line/callback`，而 OAuth cookie path 設為 `/api/java/api/auth/line`。

後續再把這個 contract 接成 Docker Compose overlay，讓本機 Web/Java/AI 三個 process 啟動後，可以用 containerized Nginx 在 `http://localhost:8088` 演練同一套路由：

```text
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.nginx.yml --profile public-proxy up -d nginx
```

再用 smoke runner 檢查 public proxy：

```text
scripts/demo-readiness.sh --base-url http://localhost:8088 --live-smoke --strict
scripts/smoke-nginx-public-proxy.sh --base-url http://localhost:8088
```

正式彩排前還要補一個不同層級的檢查：乾淨 MySQL schema 能不能讓 Java/Flyway 從零啟動。這不是 Nginx 問題，但它是 demo 現場最容易被忽略的部署風險。`scripts/smoke-clean-mysql-migrations.sh` 會建立短命 MySQL database、用臨時 port 啟 Java、等 `/actuator/health` 回 `UP`，最後停止 Java 並刪掉 database：

```text
scripts/smoke-clean-mysql-migrations.sh --timeout 180
```

這個檢查特別抓得到 seed data 和 migration 假設漂移；例如 taxonomy backfill 不應假設每個 allowlist shop id 在所有乾淨 DB 都存在。

後續再把同一個檢查接成 GitHub Actions 手動 workflow。它在 GitHub runner 裡啟 Redis / RabbitMQ / MySQL，再呼叫同一支 smoke script：

```text
.github/workflows/clean-mysql-migration-smoke.yml
```

這讓「乾淨 DB 可啟動」不只靠我的筆電狀態，也能在 reviewer 熟悉的 CI 介面重現。

## 7. 我學到的事

**公開展示部署是產品的一部分。** 外部使用者打得開，才有機會看到功能。

**LINE 設定錯誤看起來像程式 bug。** 其實可能是 channel type、callback URL、Published 狀態或 tester 權限。

**proxy 會改變 auth 細節。** OAuth state cookie path 這種小地方，足以讓整個登入失效。

**健康檢查要公開驗證。** local UP 不代表 public proxy UP。

**migration 要用乾淨 schema 驗。** 已有資料的本機 DB 會掩蓋 Flyway backfill 對 seed data 的隱性假設。

## English Version

# Case Study 11: Public Deployment Rehearsal — From Local Runtime to External Access

Before a presentation, the biggest risk is not missing features. It is the demo not opening. ByteBites needed Web, Java, AI, RabbitMQ, Qdrant, LINE Login, LINE Messaging API, CORS, callback URLs, ngrok, and public health checks to align.

The key bug was OAuth cookie path under proxy. Java used `/api/auth/line`, but the public Web proxy exposed `/api/java/api/auth/line`. The LINE OAuth state cookie would not be sent back unless the cookie path was configurable.

LINE Developers also required clear separation between Messaging API and LINE Login channels. The login channel had to be Published so classmates could sign in without tester roles.

The later deployment boundary is to keep ngrok for temporary local tunnels and use Nginx, or an equivalent managed reverse proxy, for stable public access. The route contract keeps `/api/java`, `/api/ai`, `/api/line`, and `/line` stable so LINE Login, Messaging API webhooks, AI streaming, and browser API calls do not drift into separate URL rules.

A formal rehearsal also needs a clean-schema migration smoke. The script creates a temporary MySQL database, starts Java on a temporary port, waits for `/actuator/health`, and drops the database afterward. That catches Flyway regressions that an already-migrated local database can hide.

The same smoke has a manual GitHub Actions workflow, so clean-schema startup can be rehearsed on a hosted runner with fresh MySQL, Redis, and RabbitMQ.

The lesson: deployment polish is not a footnote. It is the difference between a working local system and a product people can actually try.
