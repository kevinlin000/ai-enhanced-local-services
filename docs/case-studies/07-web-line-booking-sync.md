# Case Study 07: Web / LINE 訂位同步 — 從兩套身份到同一個交易狀態

**TL;DR** ByteBites 最難的地方不是做出一張訂位卡，而是讓 Web、LINE Login、LINE Messaging API、Java booking、AI agent、付款、取消與通知都指向同一個使用者與同一筆訂位。這篇記錄如何把兩套 LINE identity 收斂成一致的交易流程。

**Tech:** Spring Boot / LINE Login / LINE Messaging API / Next.js / FastAPI / JWT / MySQL / contract tests  
**Repo:** `backend-java/`, `ai-service-python/app/line_bot.py`, `web/app/ai/page.tsx`, `web/components/BookingButton.tsx`

## 1. 問題：Web 登入和 LINE Bot 不是同一個人

LINE 生態裡容易踩到一個陷阱：

- LINE Login 會給 Web 登入身份。
- LINE Messaging API webhook 會給 bot user id。
- 兩者在不同 channel 下不一定自然等於同一個系統 user。

早期狀態下，使用者可以在 Web 建立訂位，也可以在 LINE bot 收到推薦；但付款、取消、通知不一定能穩定回到同一個人。

這在 demo 裡會很致命。使用者看到「訂位成功」但 LINE 沒收到通知，或 LINE 卡片點進去不是同一筆狀態，信任感會直接掉下來。

## 2. 決策：交易狀態以後端為準，前端和 LINE 只是入口

我把設計原則定成：

1. Booking status 存在 Java backend。
2. Payment/cancel/update 都要回寫同一筆 booking。
3. Web card 和 LINE card 都不能各自創造狀態。
4. AI narrative 和 rendered cards 不能分離。
5. LINE notification failure 不應讓 booking DB 狀態倒退。

這讓 Web / LINE 從「兩個體驗」變成「兩個入口」。

## 3. 修身份：從通知不到人，到可綁定 booking owner

相關演進包含：

- `fix(booking): create valid LINE users`
- `fix(line): bind bookings to logged-in users`
- `fix(auth): merge line login identities`
- `fix(sync): secure line web identity flow`
- `fix(booking): sync LINE booking ownership`
- `fix(booking): link LINE bot identity`

核心是建立可追蹤的 owner：

```text
Web LINE Login user
  -> ByteBites user
  -> booking.user_id
  -> line_user_id / notification target
```

LINE bot 互動也要能回到同一份使用者資料，而不是每次用 webhook event 臨時判斷。

## 4. 修交易：付款與取消不是 UI 狀態

付款和取消最怕只改前端。

我把流程收斂為：

```text
Booking created
  -> PENDING_PAYMENT / CONFIRMED
  -> demo payment writes backend status
  -> backend publishes/sends LINE notification
  -> Web my-bookings reads backend status
```

取消也是同理：

```text
cancel request
  -> backend validates booking code / owner / state
  -> status = CANCELED
  -> LINE cancellation notice
  -> availability notification can react to released slot
```

相關 commit：

- `fix(booking): sync payment notifications to LINE`
- `fix(booking): push cancel notice to LINE bot id`
- `fix(booking): confirm cancellation lifecycle`
- `fix(sync): align availability and web cards`
- `test(sync): cover web line booking flows`
- `test(web): cover booking sync views`

## 5. 修 AI follow-up：使用者不會照工程師格式講話

LINE 對話最大的問題是使用者會說：

```text
那我要第 2 家
明天晚上
4 人
取消剛剛那筆
```

如果 Agent 每次都把訊息當成新 query，就會不知所云。

後續修了：

- retain recommendation context
- support ordinal followups
- route exact shop bookings
- parse weekday booking dates
- reject same-day booking followups
- confirm booking cancellations
- preserve locked booking selection
- preserve clarification drafts

這些不是小修，而是讓 AI 從「問答機器人」走向「能處理任務狀態的 agent」。

## 6. 測試策略：鎖 contract，不只測畫面

我補的測試重點不是「按鈕存在」，而是 contract：

- Agent done payload 有一致欄位。
- Web render 的 booking/payment 狀態和 backend 一致。
- LINE notification webhook payload 可被正確處理。
- payment transaction id 不會只停在前端。
- cancellation lifecycle 會同步到 LINE。

相關 commit：

- `test(agent): lock final payload contract`
- `test(web): cover agent response contract`
- `test(web): cover ai payment transaction`
- `test(java): cover line notification webhooks`
- `test(sync): cover web line booking flows`

## 7. 我學到的事

**聊天介面不能自成一套狀態。** LINE bot 是入口，不是 database。

**Demo payment 也要回寫真狀態。** 即使金流是 demo authorization，狀態 contract 仍要像真的一樣。

**使用者 follow-up 是 agent 的核心。** 不能只靠 single-turn prompt，看似小語句其實都帶上下文。

**一致性比酷炫更重要。** 現場 demo 最怕的是 Web 顯示已付款，LINE 還說待付款。

## English Version

# Case Study 07: Web / LINE Booking Sync — From Two Identities to One Transaction State

The hard part was not rendering a booking card. The hard part was making Web, LINE Login, LINE Messaging API, Java booking APIs, AI agent responses, payment, cancellation, and notifications all point to the same user and the same booking state.

The design decision was to make the Java backend the source of truth. Web and LINE are entry points, not separate state stores. Booking creation, payment, cancellation, and notifications all resolve back to backend booking records.

The LINE identity model required care because LINE Login and LINE Messaging API can produce different identities depending on channel configuration. The system had to merge login users, bot users, booking owners, and notification targets.

The AI agent also had to evolve from single-turn recommendations to stateful task handling: ordinal follow-ups, exact-shop bookings, weekday date parsing, cancellation confirmation, and preserved booking drafts.

The lesson: a serious AI agent is not just language quality. It is state management, identity binding, transaction consistency, and contract tests.
