# Case Study 11: 公開 Demo 部署 — 最後一哩不是上線，是可被同學打開

**TL;DR** 專題發表前，最大的風險不是功能少，而是現場打不開。ByteBites 需要 Web、Java、AI、RabbitMQ、Qdrant、LINE Login、LINE bot、CORS、callback URL、ngrok public URL 全部對齊。這篇記錄如何把本機系統整理成可展示的公開 demo。

**Tech:** Next.js rewrites / Spring Boot config / ngrok / Docker Compose / LINE Developers / health checks  
**Repo:** `web/README.md`, `docker-compose.yml`, `backend-java/src/main/resources/application.yaml`

## 1. 問題：本機能跑，不代表同學能看

本機開 `localhost:3000` 很容易，但同學需要公開 HTTPS URL。LINE Login 和 Messaging API 也需要公開 callback/webhook。

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

這一步很重要：如果 channel 還在 Developing，同學不一定能登入。

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

## 6. 我學到的事

**Demo deployment 是產品的一部分。** 教授和同學打得開，才有機會看到功能。

**LINE 設定錯誤看起來像程式 bug。** 其實可能是 channel type、callback URL、Published 狀態或 tester 權限。

**proxy 會改變 auth 細節。** OAuth state cookie path 這種小地方，足以讓整個登入失效。

**健康檢查要公開驗證。** local UP 不代表 public proxy UP。

## English Version

# Case Study 11: Public Demo Deployment — The Last Mile Is Openability

Before a presentation, the biggest risk is not missing features. It is the demo not opening. ByteBites needed Web, Java, AI, RabbitMQ, Qdrant, LINE Login, LINE Messaging API, CORS, callback URLs, ngrok, and public health checks to align.

The key bug was OAuth cookie path under proxy. Java used `/api/auth/line`, but the public Web proxy exposed `/api/java/api/auth/line`. The LINE OAuth state cookie would not be sent back unless the cookie path was configurable.

LINE Developers also required clear separation between Messaging API and LINE Login channels. The login channel had to be Published so classmates could sign in without tester roles.

The lesson: deployment polish is not a footnote. It is the difference between a working local system and a product people can actually try.
