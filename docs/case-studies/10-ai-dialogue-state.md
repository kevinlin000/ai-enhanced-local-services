# Case Study 10: AI 對話狀態 — 從單輪問答到可完成任務的 Agent

**TL;DR** 使用者不會照工程師格式輸入。他們會說「第 2 家」「明天晚上」「我要青田七六」「取消剛剛那筆」。ByteBites 的 AI 一開始常把 follow-up 當成新問題，後來才逐步補上 recommendation context、ordinal locking、booking draft、clarification policy 與 cancellation confirmation。

**Tech:** FastAPI / Gemini Agent / dialogue state / Web AI / LINE Messaging API / regression tests  
**Repo:** `ai-service-python/app/main.py`, `ai-service-python/tests/test_line_recommendation_fallback.py`

## 1. 起點：推薦看似可以，對話一長就壞

單輪 query 通常可行：

```text
推薦大安區適合聊天的餐廳
```

但真實使用者會接著說：

```text
那我要第 2 家
明天晚上 7 點
4 人
```

早期 Agent 會忘記上一輪的推薦，把「第 2 家」當成一個沒有上下文的新搜尋。結果就是不知所云，或推薦和訂位對不上。

## 2. 第一層：保留 recommendation context

第一步是把上一輪推薦的 shop ids、排序、query、卡片資料保留下來。

```text
last_recommendation:
  query: 大安區適合聊天
  shops: [10143, 10634, 10673]
```

這讓「第 2 家」可以 resolve 成確定店家，而不是讓模型猜。

## 3. 第二層：ordinal locking

光保留 context 不夠，還要鎖住使用者選擇。

如果使用者說：

```text
我要第 2 家
```

系統不應該下一輪重新排序後把第 2 家換掉。這就是 `lock ordinal booking selections` 這類修正背後的原因。

## 4. 第三層：booking draft

訂位需要多個欄位：

```text
shop
date
time
people
driving preference
```

使用者通常不會一次講完。因此 Agent 需要 booking draft：

```text
已知：青田七六 / 明天 / 晚上 / 4 人
缺少：精確時間
下一步：追問時間
```

這和一般聊天機器人不同。它不是單純生成回覆，而是在累積任務狀態。

## 5. 第四層：拒絕危險模糊

有些模糊可以追問，有些模糊要拒絕直接執行。

例如 same-day booking：

```text
今晚 7 點
```

如果現在已經過了可接受時間，或日期語意不清，系統不能硬訂。後來加了 same-day follow-up rejection 與 weekday date parsing，讓 Agent 更像客服而不是文字接龍。

## 6. 第五層：取消要確認

取消訂位是 destructive action。使用者說：

```text
取消剛剛那筆
```

系統應該先確認目標訂位，再執行。這不是禮貌問題，是交易安全。

## 7. Regression tests

這一系列修正最後靠測試鎖住：

- vague need should ask clarification。
- ordinal follow-up should resolve to previous card。
- exact shop correction should update target。
- booking draft should preserve missing fields。
- cancellation should require confirmation。
- legacy seed should not return。
- cuisine hard constraints should apply。

## 8. 我學到的事

**AI Agent 的核心不是回答，而是狀態。** 沒有 state，所有 follow-up 都會變成新問題。

**使用者自然語言充滿省略。** 「第 2 家」對人類很清楚，對系統必須有 context。

**不是每件事都該自動做。** 訂位和取消都需要明確性，模糊時追問比裝懂更高級。

**客服 AI 的高級感來自可靠。** 文案漂亮但訂錯店，比直接追問更糟。

## English Version

# Case Study 10: AI Dialogue State — From Single-Turn Answers to Task Completion

The agent initially worked for single-turn recommendation queries, but failed when users spoke naturally: "the second one", "tomorrow night", "book Qing Tian 76", or "cancel the previous one."

The fix was not a better prompt alone. The agent needed state: recommendation context, ordinal locking, booking drafts, clarification policy, date parsing, and cancellation confirmation.

This transformed the AI from a chatbot into a task-oriented agent. It can remember the previous recommendation set, resolve ordinal choices, preserve missing booking fields, ask the next relevant question, and avoid destructive actions without confirmation.

The lesson: the quality of a customer-service AI is not just language fluency. It is state, safety, and reliability across follow-up turns.
