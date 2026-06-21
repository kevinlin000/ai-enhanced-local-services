# Case Study 08: 停車提醒與車位保留展示 — 把用餐流程延伸到出發前

**TL;DR** 訂餐廳的痛點不只在「找哪家」和「有沒有位」。台北鬧區還有一個現實問題：到了附近找不到停車位。ByteBites 把訂位後的 driving preference、附近停車場、即時空位提醒、LINE notification 串成一條產品故事，並用展示版 spot hold 說明未來可預約車位的方向。

**Tech:** Spring scheduled job / Taipei parking data / LINE push / Next.js shop detail / booking preference / demo state processing  
**Repo:** `backend-java/`, `ai-service-python/app/line_bot.py`, `web/components/ShopDetailTabs.tsx`

## 1. 為什麼停車是好題目

很多餐廳產品只處理到「訂位成功」。但使用者真正的流程是：

```text
選餐廳 -> 訂位 -> 出發 -> 停車 -> 入座
```

如果餐廳在中山、信義、大安這類鬧區，停車會直接影響準時入座。這讓停車提醒成為 ByteBites 很好的差異化：它不是另一個餐廳列表，而是處理用餐前後流程的 AI operations platform。

## 2. 設計：訂位時先問，不要事後猜

我沒有在每筆訂位都硬推停車資訊，而是在訂位流程加入 driving preference：

```text
訂位完成前/後：是否會開車？
  yes -> 建立 parking reminder eligibility
  no  -> 不打擾
```

這有兩個產品好處：

- 使用者不開車時不收到無關通知。
- 系統知道何時該把「餐廳推薦」延伸成「出發輔助」。

## 3. Reminder timing：不是每秒推播，而是可解釋的查詢時資料

台北市停車資料有上游更新頻率限制。ByteBites 不假裝自己每秒掌握真實車位，而是採用：

- Java scheduled job 每 5 分鐘掃描需要提醒的訂位。
- 訂位前約 2 小時觸發 reminder。
- 查詢當下使用最新快取/上游資料。
- LINE message 明確呈現附近停車場與剩餘車位。

這是負責任的展示設計：產品體驗成立，但不誇大資料即時性。

## 4. API 與 contract

停車功能不是寫死在 LINE 文案裡，而是進入後端 contract：

```text
PATCH /api/booking/{bookingCode}/parking-preference
POST  /internal/line/parking-reminder
```

流程：

```text
Booking
  -> user says will drive
  -> Java stores preference
  -> scheduler finds upcoming booking
  -> parking service finds nearby lots
  -> LINE reminder sent
```

前端 detail page 也顯示附近停車場，讓 Web 和 LINE 的資訊不是兩套世界。

## 5. 展示版 spot hold：可以展示，但要誠實

後續提出「停車通知後能不能預約車位」這個想法。真實世界裡確實有部分停車場支援預約，但不普遍，也不是台北開放資料本身能完成的事。

因此合理方案是做展示版 hold：

- 使用者在 LINE 或 Web 點「預約車位」。
- 顯示展示版保留成功。
- 回傳停車場名稱、樓層、區域、格位編號。
- 前端畫面把可用格數減 1。
- LINE 發送確認訊息。
- 文案保留展示語意，不假裝真的串到停車場營運商。

這讓產品願景很清楚，同時避免誠信風險。

## 6. 這個功能在簡報中的價值

停車提醒很適合當壓軸，因為它回答了：

```text
你們和一般餐廳推薦網站差在哪？
```

答案不是「我們也有 AI」。答案是：

```text
我們把用餐決策延伸到實際出發前的下一個痛點。
```

推薦、訂位、付款、候補、停車提醒連成一條線，ByteBites 才像一個產品，而不是多個功能拼貼。

## 7. 我學到的事

**好功能不一定是最大功能。** 停車提醒技術上不如 AI agent 複雜，但產品記憶點很強。

**資料限制要說清楚。** 開放資料有更新頻率，不能把它包裝成每秒保證車位。

**展示整合可以是假的，但 contract 要真。** UI 可以展示 spot hold，後端狀態與訊息格式仍應像真流程設計。

**差異化來自流程延伸。** 從「推薦餐廳」延伸到「準時抵達」，產品定位就不一樣了。

## English Version

# Case Study 08: Parking Reminder and Demo Spot Hold — Extending Dining Flow Before Arrival

Restaurant booking does not end at reservation. In dense Taipei districts, finding parking can determine whether the user arrives on time. ByteBites turns that into a product differentiator by asking for driving preference, showing nearby parking lots, sending reminders before the booking, and demonstrating a future parking spot hold flow.

The design is intentionally responsible. Taipei parking availability depends on upstream data refresh intervals, so ByteBites does not claim second-by-second accuracy. The Java scheduler scans upcoming bookings, triggers reminders roughly two hours before reservation time, and uses the latest available cache/upstream data.

The demo spot hold flow is a product concept: show a successful reservation with parking lot name, floor, zone, and spot number, decrement the displayed availability, and send a LINE confirmation. It is clearly a demo integration rather than a false claim of real parking operator reservation.

The lesson: the most memorable feature is not always the most complex one. Parking turns ByteBites from a restaurant recommendation site into an end-to-end dining operations product.
