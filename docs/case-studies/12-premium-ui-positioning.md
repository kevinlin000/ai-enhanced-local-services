# Case Study 12: Premium UI 不是變成 inline clone — 找回 ByteBites 的品牌定位

**TL;DR** ByteBites 曾經往 inline-style 方向靠攏：精品餐廳、大留白、金色、極簡卡片。但做著做著發現，這會讓產品看起來像另一個餐廳展示平台。最後我把定位拉回「AI 會推薦，也會安排」：保留高級質感，但讓 UI 與文案突出 AI 訂位、付款、候補、停車與 LINE 同步的差異化。

**Tech:** Next.js / Tailwind / typography system / product positioning / UX writing  
**Repo:** `web/app/page.tsx`, `web/app/ai/page.tsx`, `web/app/shops/page.tsx`, `web/app/globals.css`

## 1. 起點：inline 很漂亮，但不能只模仿

inline 的設計強在：

- 品牌乾淨。
- 餐廳質感高。
- 首頁留白舒服。
- 分類入口清楚。
- 使用者一眼知道是訂位產品。

ByteBites 早期一度採用類似語氣：

```text
獨家桌位，僅此一處
餐飲體驗 臻於極致
今晚想去哪？
```

這些句子單看不錯，但問題是它們把 ByteBites 推向「高級餐廳展示」的方向，反而弱化了我們真正不同的地方：AI workflow。

## 2. 問題：高級感和差異化不是同一件事

如果 ByteBites 只做得像 inline，審查者很容易問：

```text
那你們和 inline 差在哪？
```

答案不能只是「我們也有 AI」。因為現在很多產品都可以加 chatbot。

真正差異應該是：

```text
ByteBites 不只推薦餐廳，它把訂位後續流程也接起來。
```

所以 UI 文案需要從「餐飲體驗」改成「用餐安排」。

## 3. 文案改版：從精品敘事到 operations 敘事

首頁 hero 改成：

```text
AI DINING OPERATIONS
會推薦
也會安排
```

Supporting copy 改成：

```text
ByteBites 以 AI 判斷用餐情境，串接餐廳搜尋、訂位付款、候補通知與停車提醒。
從選店到出發，每一步都有明確下一步。
```

這個版本保留高級感，但更清楚說出產品能力。

## 4. 字體策略：UI 清楚，大標題有質感

我沒有全站換成明體或花體。原因：

- 表單、篩選器、後台、付款頁需要高可讀性。
- LINE / Web contract 狀態文字不能因字體變得難讀。
- 展示環境不應依賴外部字體下載。

最後策略：

```css
body:
  Noto Sans TC

hero / AI empty state:
  Songti TC -> Noto Serif TC -> PingFang TC fallback
```

也就是 UI 用黑體保持清楚，大標題用宋體系增加精品感。這比全站套一個「漂亮字體」更穩。

## 5. 探索頁：不要像聊天，也不要像 inline

原本探索頁容易出現「AI 語意」「快速情境」這種聊天產品語氣。後來改成：

```text
條件篩選
需求排序
常用決策模板
餐廳探索
```

這讓 Web 探索頁像資料決策工具，而不是 LINE bot 的複製版。

LINE 裡可以像服務生追問；Web 裡應該像高效率控制台。兩者後端 contract 一致，但前端語氣不用一樣。

## 6. Logo 與主視覺取捨

新的主視覺圖很適合：

- 簡報封面。
- LINE rich menu / banner。
- 首頁 hero campaign。
- 說明「訂位 + 定位 + 停車 + 通知」的產品概念。

但我不建議完全取代 `B` monogram。原因：

- `B` 在 LINE 頭像、favicon、小尺寸 sidebar 更穩。
- 新圖資訊量高，適合 campaign，不一定適合 brand mark。
- 展示時需要一個高辨識、小尺寸也清楚的核心 logo。

最佳策略：

```text
B monogram = brand identity
好好訂主視覺 = product campaign visual
```

## 7. 我學到的事

**質感不是複製競品。** 可以學節奏、留白和克制，但定位要回到自己的產品能力。

**文案是產品架構的一部分。** `今晚想去哪？` 和 `會推薦，也會安排` 會導向完全不同的期待。

**中文字體要分層使用。** 大標題可以更有風格，操作介面要保持清楚。

**品牌識別和活動視覺不同。** 小 logo 要穩，主視覺要講故事。

## English Version

# Case Study 12: Premium UI Without Becoming an inline Clone

ByteBites initially moved toward an inline-style premium dining aesthetic: large whitespace, gold accents, refined restaurant language, and editorial wording. It looked polished, but it risked becoming another restaurant showcase.

The key product decision was to keep the premium visual quality while reclaiming ByteBites' own positioning: AI does not only recommend; it arranges the dining flow. The homepage language changed from luxury dining copy to operational intelligence: "AI Dining Operations", "會推薦，也會安排".

Typography followed the same principle. The UI remains on Noto Sans TC for clarity, while hero-scale display text uses a serif-style Chinese fallback stack such as Songti TC. This adds refinement without hurting forms, filters, booking flows, and merchant tools.

The student-proposed visual direction is strong as campaign imagery because it clearly communicates reservation, location, parking, and notification. But the existing `B` monogram remains better for favicon, LINE avatar, and small UI contexts.

The lesson: premium design is not copying a competitor. It is using visual restraint to make the product's own promise feel credible.
