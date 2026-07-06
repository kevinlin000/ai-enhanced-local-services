# AWS 部署 Runbook（單機 staging，照序執行）

目標：`https://<PUBLIC_DOMAIN>` 上跑完整 ByteBites（Web + Java + AI + LINE）。
架構：EC2 一台 + docker compose 七容器 + 主機 Nginx + Let's Encrypt。
路由契約沿用 `docs/deployment-aws.md`；Nginx 設定用 `deploy/nginx/bytebites.conf.template` 渲染。

**執行者注意**：每一步結束都有驗證命令，驗證不過不要進下一步。

## 0. 前置（本地機器）

1. 匯出 MySQL 資料（600 家店與所有業務資料都在 DB，AWS 上不重爬）：

   ```bash
   docker exec bytebites-mysql sh -c 'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction hmdp' | gzip > /tmp/hmdp-$(date +%Y%m%d).sql.gz
   ```

2. 匯出 Qdrant collection snapshot：

   ```bash
   curl -X POST http://localhost:6333/collections/bytebites_shops/snapshots
   # 回傳 snapshot 名稱後：
   curl -o /tmp/bytebites_shops.snapshot \
     http://localhost:6333/collections/bytebites_shops/snapshots/<snapshot-name>
   ```

3. 準備新 secrets（**全部輪換**，舊值已暴露在開發過程）：LINE Developers Console 重發
   Login channel secret 與 Messaging channel secret/access token；`openssl rand -hex 32`
   產 JWT/內部 secrets；Google AI Studio 重發 GEMINI_API_KEY。
   TapPay sandbox 另需前端 App ID/App Key（`NEXT_PUBLIC_TAPPAY_*`）與後端
   Partner Key/Merchant ID；前端不可使用 Partner Key。

## 1. AWS 資源

- EC2：**t4g.large**（ARM, 2vCPU/8GB, Ubuntu 24.04）+ 30GB gp3。
- Security Group：inbound 只開 22（限自己 IP）、80、443。
- Elastic IP 綁定。
- DNS：Route 53 或 DuckDNS 把 `<PUBLIC_DOMAIN>` A record 指到 Elastic IP。

驗證：`dig +short <PUBLIC_DOMAIN>` 回 Elastic IP。

## 2. 主機初始化（EC2 上）

```bash
sudo apt update && sudo apt install -y docker.io docker-compose-v2 nginx certbot python3-certbot-nginx gettext-base
sudo usermod -aG docker ubuntu && newgrp docker
git clone https://github.com/kevinlin000/ai-enhanced-local-services.git ~/bytebites
```

## 3. 應用啟動

```bash
cd ~/bytebites/deploy/aws
cp .env.prod.example .env.prod
vim .env.prod        # 填入第 0 步準備的全部 secrets 與 PUBLIC_DOMAIN
docker compose --env-file .env.prod up -d --build
```

ARM 注意：三個 Dockerfile 基底（temurin/python-slim/node-alpine）都有 arm64 版，直接 build 即可。

驗證：

```bash
curl -s http://127.0.0.1:8081/actuator/health   # {"status":"UP"}（Flyway 會自動建 schema）
curl -s http://127.0.0.1:8000/health
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:3000/
```

## 4. 資料還原

```bash
# MySQL（覆蓋 Flyway 建好的空表；dump 內含 flyway_schema_history，版本一致）
gunzip -c hmdp-*.sql.gz | docker compose --env-file .env.prod exec -T mysql \
  sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" hmdp'

# Qdrant snapshot 還原
curl -X POST 'http://127.0.0.1:6333/collections/bytebites_shops/snapshots/upload?priority=snapshot' \
  -H 'Content-Type: multipart/form-data' -F 'snapshot=@bytebites_shops.snapshot'

docker compose --env-file .env.prod restart java ai
```

驗證：

```bash
curl -s http://127.0.0.1:8081/api/shop/count          # data 應為 ~600
curl -s http://127.0.0.1:6333/collections/bytebites_shops | grep -o '"points_count":[0-9]*'
curl -s -X POST http://127.0.0.1:8000/api/ai/search -H 'Content-Type: application/json' \
  -d '{"query":"信義區火鍋","top_k":3}'               # hits 非空
```

## 5. Nginx + TLS

```bash
cd ~/bytebites
SERVER_NAME=<PUBLIC_DOMAIN> WEB_UPSTREAM=127.0.0.1:3000 \
JAVA_UPSTREAM=127.0.0.1:8081 AI_UPSTREAM=127.0.0.1:8000 CLIENT_MAX_BODY_SIZE=10m \
envsubst '$SERVER_NAME $WEB_UPSTREAM $JAVA_UPSTREAM $AI_UPSTREAM $CLIENT_MAX_BODY_SIZE' \
  < deploy/nginx/bytebites.conf.template | sudo tee /etc/nginx/conf.d/bytebites.conf
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d <PUBLIC_DOMAIN>
```

驗證：`curl -sI https://<PUBLIC_DOMAIN>/ | head -1` 回 200。

## 6. LINE Console 切換

LINE Developers Console：

- Login channel → Callback URL：`https://<PUBLIC_DOMAIN>/api/java/api/auth/line/callback`
- Messaging API channel → Webhook URL：`https://<PUBLIC_DOMAIN>/api/line/webhook`，按 Verify。

驗證：手機 LINE 對 bot 發「信義區火鍋」收到推薦卡片；網站用 LINE 登入成功。

## 6.5 TapPay Sandbox IP 白名單

TapPay pay-by-prime 會驗證**後端 server 的來源 IP**。EC2 的 Elastic IP 固定，
所以只需設定一次：

1. 登入 [TapPay Portal](https://portal.tappaysdk.com/)（sandbox）。
2. 商家管理 → 對應 Merchant → Server IP 白名單 → 加入 EC2 的 Elastic IP。

驗證：網站上走一次信用卡補款／訂金流程（測試卡 4242…），不再出現
「TapPay sandbox IP 未在商家後台白名單內」。
（本機開發因 IP 浮動無法固定白名單，demo 錢包路徑不受影響。）

## 7. 終驗

```bash
cd ~/bytebites
scripts/demo-readiness.sh --base-url https://<PUBLIC_DOMAIN> --live-smoke --strict
```

再手動走一輪：AI 找店 → 訂位 → 付款（TapPay sandbox 卡號）→ LINE 通知 → 我的訂位/我的餐券 → 商家後台。

## 8. 收尾與維運

- `docker compose --env-file .env.prod ps` 全部 healthy 後，設開機自啟：
  compose 服務已寫 `restart: unless-stopped`，Docker daemon enable 即可
  （`sudo systemctl enable docker`）。
- 每日 DB 備份 cron：
  `docker compose exec -T mysql sh -c 'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction hmdp' | gzip > ~/backups/hmdp-$(date +\%F).sql.gz`
- 本地開發環境維持 ngrok 不變；AWS 是展示環境，兩邊 LINE channel 若共用，
  webhook 只能指一邊——展示期指 AWS。

## 回滾

任一步壞掉：`docker compose --env-file .env.prod down`（volume 保留），修正後重新 up。
資料損壞：從第 8 步的備份 gunzip 還原。

## 明確不做（本階段）

- RDS / ElastiCache / ECS（Stage 2，見 docs/deployment-aws.md）
- strict-mode 開啟（商家後台 demo 需要免認證，見 ADR 0002）
- CloudFront（單機 nginx 已足夠 demo 流量）
