# ByteBites Presentation Guide

> Goal: help the audience understand that ByteBites is not a chatbot demo. It is a full dining operations product: data, AI, booking, LINE, payment state, notification, parking, and deployment.

## 1. One-Minute Thesis

**中文**

ByteBites 想解決的不是「找一家餐廳」而已，而是整個用餐安排流程。使用者用自然語言說出需求，AI 先判斷地點、料理、人數、場合與時間，再整理候選餐廳，接著把訂位、訂金付款、LINE 通知、候補、取消與停車提醒串在同一條流程裡。這個專案累積 522 次 commit，包含資料爬蟲、語意搜尋、評論分析、Web/LINE 身份同步、交易狀態 contract、商家後台與公開 demo 部署。

**English**

ByteBites is not just a restaurant finder. It connects the dining journey from natural-language intent to recommendation, booking, demo deposit payment, LINE notifications, waitlist, cancellation, and parking reminders. Across 522 commits, the project evolved into a full-stack AI dining operations platform with data pipelines, semantic search, review intelligence, identity sync, transaction contracts, merchant tooling, and public demo deployment.

## 2. Suggested 7-Minute Flow

### 0:00-0:45 — Problem

Most restaurant products stop at discovery. The user still has to decide, book, pay, remember status, wait for seats, and solve parking.

Key sentence:

```text
我們不是只問「今晚想吃什麼」，而是問「怎麼把這餐安排到真的能成行」。
```

### 0:45-1:45 — Product Demo Overview

Show homepage or Web AI first.

Use one high-signal query:

```text
推薦大安區美式漢堡
```

Then one ambiguous query:

```text
推薦7人聚餐餐廳
```

Explain that the first query should search directly, while the second should ask for missing details.

### 1:45-3:00 — AI Is Workflow, Not Chat

Show that the agent handles:

- intent extraction;
- cuisine/district constraints;
- semantic search and rerank;
- recommendation cards;
- booking draft;
- follow-up context.

Key sentence:

```text
客服 AI 的高級感不是一直講很多話，而是知道什麼時候查資料、什麼時候追問、什麼時候不能亂做。
```

### 3:00-4:15 — Data Quality

Show `docs/data-coverage-report.md` or mention the numbers:

- 600 active Taipei shops;
- media coverage 100%;
- AI summary coverage 100%;
- ABSA / Mongo review coverage 99.8%;
- price signal coverage 86.3%;
- legacy seed removed from recommendation path.

Key sentence:

```text
AI 推薦的上限不是 prompt，而是資料覆蓋率、分類正確性與 payload 一致性。
```

### 4:15-5:30 — Booking, LINE, Payment, Parking

Show the end-to-end flow:

```text
AI 推薦 -> 訂位 -> demo 付款 -> LINE 通知 -> 候補/取消 -> 停車提醒
```

Mention that Web and LINE are different entrances into the same backend booking state.

### 5:30-6:30 — Engineering Evidence

Use the case studies as proof:

- true SSE streaming;
- ABSA F1 0.955;
- model ablation;
- taxonomy migrations;
- Web/LINE identity sync;
- public demo deployment;
- AI concierge quality hardening.

### 6:30-7:00 — Closing

End with product positioning:

```text
ByteBites 不是另一個餐廳列表，也不是單純聊天機器人。它是會推薦，也會安排的 AI 用餐營運平台。
```

## 3. Demo Script

Use this order to reduce live-demo risk.

### Demo A — Clear Need

Prompt:

```text
推薦大安區美式漢堡
```

What to point out:

- It should search immediately.
- It should not ask generic questions first.
- It should explain why the result fits district and cuisine.

### Demo B — Vague Group Need

Prompt:

```text
推薦7人聚餐餐廳
```

What to point out:

- A weak bot invents answers.
- A better concierge asks for location, date, time, and occasion.
- This is a safety and quality behavior, not a failure.

### Demo C — Contextual Need

Prompt:

```text
大安區適合聊天聚餐
```

What to point out:

- Ranking should favor quiet/chat-friendly places.
- Context should beat generic popularity.
- Web card and AI text should align.

### Demo D — Booking and LINE

Pick a recommendation, enter:

```text
明天晚上 7 點 4 人
```

Then show:

- booking state;
- demo payment state;
- LINE notification;
- parking preference if driving.

## 4. Proof Table

| Claim | Evidence |
|---|---|
| Not a static UI demo | Spring Boot backend, FastAPI AI, Next.js frontend, MySQL, Redis, RabbitMQ, Qdrant |
| AI quality is engineered | `docs/case-studies/10-ai-dialogue-state.md`, `13-ai-concierge-quality-hardening.md` |
| Data quality is measured | `docs/case-studies/06-data-crawler-coverage.md`, `docs/data-coverage-report.md` |
| Recommendations use structure | `recommended_shop_ids`, taxonomy constraints, Qdrant payload sync |
| Web/LINE are synchronized | `docs/case-studies/07-web-line-booking-sync.md` |
| Deployment was made testable | `docs/case-studies/11-demo-deployment.md` |
| Design has product judgment | `docs/case-studies/05-recommendation-ux.md`, `12-premium-ui-positioning.md` |
| Claims are reviewable | `docs/portfolio-evidence-map.md`, `scripts/verify-portfolio.sh`, `.github/workflows/portfolio-ci.yml` |

## 5. What to Say If Asked About Limits

Be honest. This actually makes the project look stronger.

- **Parking reservation**: current spot hold is a demo product concept. It does not claim real parking operator reservation.
- **Payment**: demo payment simulates authorization and state transitions; it is designed to prove contract flow.
- **Parking availability**: based on upstream/cache refresh cadence, not second-by-second guaranteed availability.
- **AI answers**: the system uses constraints, reranking, tests, and fallback policies, but recommendation is still advisory.
- **Security**: demo mode is convenient for presentation; production deployment should tighten demo headers, internal secrets, JWT storage, and endpoint authorization.

## 6. Roadmap With High Product Value

Highest value next:

1. **Private preference memory**  
   Store "likes quiet seats", "no cilantro", "avoid this shop", "prefers Japanese on Fridays".

2. **Private AI-matched offers**  
   Not public coupons. Trigger offers only for likely churn, off-peak capacity, or high-intent users.

3. **Conversational booking changes**  
   User says "改 8 點，同樣 4 位", AI checks availability and updates the booking.

4. **Group decision flow**  
   A share link where group members vote on time, budget, district, and dietary restrictions.

5. **Incident handling**  
   If the restaurant delays a table or the user is late, AI coordinates alternatives and updates LINE.

## 7. Final Positioning

Use this as the last slide:

```text
ByteBites
AI Dining Operations Platform

會推薦，也會安排。
從選店、訂位、付款、候補、通知到停車提醒，
讓一次用餐從想法變成可執行的流程。
```

English version:

```text
ByteBites
AI Dining Operations Platform

Not only recommendations, but arrangements.
From discovery to booking, payment, waitlist, notification, and parking guidance,
ByteBites turns dining intent into an executable workflow.
```
