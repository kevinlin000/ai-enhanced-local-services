# ByteBites Recording Script

This is the script to record the portfolio walkthrough.

Recommended format:

```text
3-5 minute screen recording
personal voiceover
no live improvisation
show proof, not every feature
```

## Recording Goal

The video should prove one thesis:

```text
ByteBites is an AI dining operations platform.
AI orchestrates the workflow, while Java owns booking, payment, incident, and refund state.
```

Do not present it as a generic restaurant chatbot or a production SaaS rollout.

## 5-Minute Walkthrough

| Time | Screen | Narration |
|---:|---|---|
| 0:00-0:20 | README or app homepage | "ByteBites is not just a restaurant recommendation demo. I built it as an AI dining operations platform: recommendation, booking, payment state, incident handling, LINE coordination, merchant operations, and verification gates." |
| 0:20-0:55 | AI chat / recommendation cards | "The AI layer handles ambiguous dining intent and retrieves grounded restaurant candidates. The important detail is that the narrative and UI cards share structured recommended shop ids, so the model text and the product surface do not drift apart." |
| 0:55-1:30 | Booking / My Bookings | "Once the user moves from discovery to booking, Java becomes the source of truth. Booking status, party size, time, payment state, and later changes are all owned by backend contracts, not by the model." |
| 1:30-2:15 | My Bookings incident or AI late-arrival prompt | "For real-time incident handling, a user can say they will be late. The system deterministically finds the recent valid booking and creates an incident in Java. The model is not allowed to guess or mutate booking state." |
| 2:15-2:55 | Merchant incident proposal | "The merchant side can see the open incident and propose an alternative slot. This turns a notification into an operational workflow. The proposal lifecycle supports pending, accepted, declined, and expired states." |
| 2:55-3:30 | LINE rescue/proposal card | "LINE is a channel, not the state owner. The Flex card gives the customer an action path, but accept or decline still calls back into Java, where the transaction validates ownership, expiry, and booking rules." |
| 3:30-4:05 | Refund operations digest | "The project also covers the less glamorous operational side: deposit adjustments, top-up, refund reconciliation, failed or stale refund visibility, escalation notes, and LINE digest notifications. I kept demo reconciliation honest instead of pretending it is a real PSP refund rollout." |
| 4:05-4:25 | Architecture overview | "The architecture boundary is the main engineering point: Next.js is the product surface, FastAPI AI orchestrates and renders cards, Java owns business state, ETL enriches data into Qdrant and MySQL, and Nginx defines the public route contract." |
| 4:25-4:40 | ER model | "The ER model I would highlight is the operational core: users, shops, bookings, incidents, deposit adjustments, refund audit events, and merchant notification dispatch. The key design is separating booking mutation from money movement." |
| 4:40-5:00 | CI / release readiness | "The portfolio release is verified by Java, AI, ETL, data-quality, Web tests, production build, Nginx route contracts, release readiness, and clean-schema migration smoke. I would treat production rollout as a separate gate: managed secrets, cloud data stores, backups, observability, real PSP refund integration, and operations policy." |

## 3-Minute Cut

Use this when the recording must be tighter.

| Time | Screen | Narration |
|---:|---|---|
| 0:00-0:20 | Homepage or README | "ByteBites is an AI dining operations platform, not just a chatbot. It covers recommendation, booking, payment state, incident handling, LINE coordination, and merchant operations." |
| 0:20-0:55 | AI recommendation | "The AI layer handles ambiguous dining requests and returns grounded recommendation cards. The text and cards share structured ids, so the UI is not free-form model output." |
| 0:55-1:25 | Booking / My Bookings | "When the user books, Java owns the state: booking, payment, reschedule, deposit adjustment, and incident data all live behind backend contracts." |
| 1:25-2:05 | Incident + merchant proposal | "If the customer says they will be late, Java creates a real incident from the latest valid booking. The merchant can propose an alternative slot, and the customer can accept or decline." |
| 2:05-2:30 | LINE card | "LINE is an action channel. The card is rendered by the AI service, but every state transition still goes through Java validation." |
| 2:30-3:00 | Architecture + CI | "The core boundary is AI orchestrates, Java owns state. The repo is verified by portfolio CI, release readiness, Nginx contracts, and clean migration smoke. Production rollout would be the next separate gate." |

## 3-Minute Voiceover Script zh-TW

Use this as the direct read-aloud version.

```text
這是 ByteBites。我把它做成一個 AI dining operations platform，而不是只有餐廳推薦的 chatbot。

第一段是 discovery。使用者可以用自然語言描述需求，例如想找適合聚餐、交通方便、評價穩定的餐廳。AI service 會處理模糊意圖，但回到產品畫面時，不是只顯示一段模型文字，而是回傳結構化的推薦店家 id，讓文字說明和推薦卡片對得起來。

第二段是訂位。只要使用者從推薦進到 booking，Java backend 就是 source of truth。訂位編號、日期時間、人數、付款狀態、改期、訂金調整，全部都由 Java contract 管，不讓模型直接改核心狀態。

第三段是臨場救場。當顧客說「我塞車會晚到 20 分鐘」，系統不會讓模型猜是哪一筆訂位，而是 deterministic 找最近有效訂位，然後由 Java 建立 incident。商家後台可以看到 open incident，提出替代時段，顧客可以接受或拒絕。

第四段是 LINE。LINE 在這裡是 action channel，不是狀態來源。Flex card 可以把救場通知送到顧客手上，但接受或拒絕仍然會回到 Java transaction，由後端驗證身份、期限、訂位規則和訂金政策。

第五段是營運面。這個專案也處理比較真實但不華麗的問題：補款、退款 reconciliation、失敗退款、SLA、escalation note，以及 refund operations digest。我沒有把 demo callback 假裝成真實 PSP rollout；production 版本會另外接真實 refund provider。

最後是架構和驗證。整體邊界是：Next.js 是產品介面，FastAPI AI service 做 orchestration 和 LINE card，Java Spring Boot 擁有 booking、payment、incident、refund state，ETL 把餐廳與評論資料整理進 MySQL 和 Qdrant，Nginx 定義公開路由邊界。

所以這個作品我會定位成 portfolio-ready：功能是完整縱切，而且有 CI、release readiness、clean MySQL migration smoke 和測試保護。但我不會誇口說它已經是 production SaaS。真的上線下一步會是 managed secrets、cloud runtime、backup、observability、真實 PSP refund provider，還有營運制度。
```

## 12-Minute Interview Version

Use this when an interviewer asks for a deeper walkthrough.

1. Product thesis: discovery is not enough; ByteBites continues into booking and operations.
2. Data layer: crawler, taxonomy, reviews, ABSA, media coverage, Qdrant payloads.
3. AI layer: retrieval, dialogue state, structured recommendation ids, clarification, deterministic routing.
4. Java state boundary: booking, payment, incident, proposal, deposit adjustment, refund operations.
5. Web/LINE channels: My Bookings, merchant console, LINE Login, Messaging API, Flex cards.
6. Incident flow: late arrival -> Java incident -> merchant proposal -> LINE/Web accept or decline.
7. Refund flow: top-up checkout, refund reconciliation, idempotency, signature, source allowlist, SLA, escalation.
8. Deployment boundary: Nginx public routes, local public proxy, smoke scripts.
9. ER model: booking code as workflow key, incident proposal state, deposit adjustment, refund audit, merchant authorization.
10. Verification: Portfolio CI, full local verification, clean MySQL migration smoke, release readiness.
11. Production plan: managed secrets, cloud runtime, backups, observability, PSP provider integration, operations policy.

## Screenshot Capture Order

Capture screenshots in the same order as the narration:

1. `00-homepage-product-thesis.png`
2. `01-ai-recommendation-cards.png`
3. `02-booking-payment-incident.png`
4. `04-merchant-proposal.png`
5. `05-line-rescue-card.png`
6. `06-refund-operations-digest.png`
7. `09-architecture-overview.png`
8. `10-er-model-booking-operations.png`
9. `07-ci-portfolio-green.png`
10. `08-clean-migration-smoke.png`

The order differs slightly from the filename order so the video ends with proof.

## Recording Checklist

Before recording:

```bash
scripts/release-readiness.sh --offline
```

If recording against a live local stack:

```bash
scripts/demo-readiness.sh --base-url http://localhost:8088 --live-smoke --strict
```

During recording:

- Keep the browser zoom at 100%.
- Use a 1440px or wider desktop viewport if possible.
- Hide browser bookmarks, unrelated tabs, notifications, and secrets.
- Do not show `.env` files, tokens, provider keys, personal accounts, or private LINE credentials.
- Keep narration calm and concrete. Mention tradeoffs only when they support the architecture thesis.

After recording:

- Export as `bytebites-portfolio-walkthrough-3min.mp4` or `bytebites-portfolio-walkthrough-5min.mp4`.
- Capture the evidence screenshots, including the ER model.
- Optionally include `00-bytebites-evidence-walkthrough.gif` as a short visual preview in the portfolio page. Keep the voiceover video as the primary artifact.
- Save the latest Portfolio CI run id with the evidence notes.
- Re-run `scripts/release-readiness.sh --offline` after any doc edits.

## Opening Lines

Use this if starting from a blank intro:

```text
This is ByteBites, an AI dining operations platform.
The project started from restaurant recommendation, but the interesting part is what happens after discovery:
booking, payment state, late-arrival incidents, LINE coordination, merchant proposals, and refund operations.
The main architecture choice is that AI can orchestrate the workflow, but Java owns business state.
```

## Closing Lines

Use this to finish without overclaiming:

```text
This is portfolio-ready because the workflow is implemented, contract-tested, and verifiable by CI and release gates.
I would not call it production SaaS yet.
For production, I would next add managed secrets, cloud data stores, backups, observability,
real PSP refund provider integration, and an operations playbook.
```
