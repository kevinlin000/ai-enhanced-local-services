# Case Study 13: AI Concierge 品質硬化 — 從會回答到可靠接待

**TL;DR** ByteBites 的 AI 一開始已經能推薦餐廳，但還不到客服等級：有時明明是餐廳需求卻先閒聊、有時模糊需求沒有追問、有時商務/聊天情境被居酒屋或燒肉壓過、有時 Web 和 LINE 的語氣不夠穩。這輪修正把 AI 從「會回答」往「可靠接待」推進：先判斷 dining intent、再做語意搜尋、保留多輪需求、對模糊資訊追問、用 cuisine/district/context rerank 壓住錯誤結果，最後用 regression tests 鎖住。

**Tech:** FastAPI / Gemini Agent / Qdrant semantic search / dialogue policy / LINE and Web AI / pytest  
**Repo:** `ai-service-python/app/main.py`, `ai-service-python/tests/test_line_recommendation_fallback.py`

## 1. 起點：AI 能聊，但不像頂級客服

使用者在 Web 或 LINE 裡不會照格式輸入。他們會說：

```text
推薦7人聚餐餐廳
大安區，適合聊天
推薦大安區美式漢堡
中山區商務宴請台菜
```

早期問題不是完全不能回答，而是不夠可靠：

- 明確餐廳搜尋有時沒有先查資料，先回通用追問。
- 「7 人聚餐」這種模糊需求沒有收斂欄位，而是急著推薦。
- 「適合聊天」容易被一般聚餐或居酒屋結果覆蓋。
- 指定料理時，向量相似度可能把不符料理混進來。
- 回覆語氣有時太像生成文字，缺少客服的穩定下一步。

頂級客服 AI 的標準不是「句子漂亮」，而是：知道自己現在掌握了什麼、缺什麼、下一步應該做什麼。

## 2. 第一個決策：明確 dining query 先查資料

如果使用者說：

```text
推薦大安區美式漢堡
```

這不是閒聊，也不是需要先問「請問你偏好什麼」。它已經有地區與料理意圖，系統應該先查資料，再用 AI 組織結果。

因此 routing policy 改成：

```text
clear dining intent
  -> extract constraints
  -> semantic search
  -> hard filters
  -> rerank
  -> concise concierge response
```

這讓 AI 不再把明確搜尋當成一般聊天。

## 3. 第二個決策：模糊需求要追問，不要裝懂

`推薦7人聚餐餐廳` 只提供人數，還缺：

- 地點
- 日期
- 時段
- 料理或場合
- 是否需要包廂或安靜

客服 AI 如果直接推薦，表面看起來快速，其實是在賭。修正後的行為是先收斂：

```text
7人我先記下。請再補地點、日期與大概時段，我會幫你篩出適合多人聚餐的餐廳。
```

這個差異很重要。高級不是永遠直接給答案，而是在資訊不足時提出最少、最關鍵的問題。

## 4. 第三個決策：情境不能被熱門度蓋過

「大安區適合聊天」不是單純「大安區熱門餐廳」。它隱含：

- 空間不能太吵
- 座位要適合久坐
- 料理不應太需要高互動烹調
- 燒肉、居酒屋、熱炒不一定是最佳答案

因此 rerank 加入 dining context：

```text
quiet/chat/business/family/date
  -> boost matching tags and summaries
  -> penalize noisy or high-turnover categories
  -> keep district and cuisine hard constraints above vibe score
```

這避免「商務台菜」混出餐酒館，也避免「聊天聚餐」被不合場景的熱門店壓過。

## 5. 第四個決策：Web 和 LINE 可以不同語氣，但同一個判斷

LINE 像聊天，Web 像工作台。兩邊不需要 UI 一樣，但底層判斷要一致：

- 同一套 intent extraction。
- 同一套 semantic search constraints。
- 同一套 recommendation IDs。
- 同一套 booking draft / CTA contract。

差別只在表達：

| Channel | Tone |
|---|---|
| LINE | 短句、明確下一步、適合手機閱讀 |
| Web AI | 更完整的推薦理由、卡片、操作入口 |

這讓產品看起來不是兩個不同 AI，而是一個 AI 在兩個通路上服務。

## 6. Regression tests 鎖住行為

這輪修正後，用測試鎖住幾個容易退化的行為：

- legacy seed 不可回到推薦。
- 明確料理 query 要進 semantic search，不可只閒聊。
- 模糊多人需求要追問地點/日期/時段。
- 指定店名或 follow-up 要保留上下文。
- Web/LINE 的 recommendation fallback 不可回傳已移除資料。

最新針對 LINE recommendation fallback 的測試：

```text
uv run pytest tests/test_line_recommendation_fallback.py
90 passed
```

## 7. Demo 中怎麼展示

建議現場不要只問「推薦餐廳」。要展示三種客服能力：

1. **明確需求**  
   `推薦大安區美式漢堡`  
   預期：直接查資料，回 1-3 家，並說明為什麼符合。

2. **模糊需求**  
   `推薦7人聚餐餐廳`  
   預期：不亂推，先收斂地點、日期、時段、料理或場合。

3. **情境需求**  
   `大安區適合聊天聚餐`  
   預期：排除太吵或不適合聊天的類型，優先安靜/聚餐/座位舒適。

這三個 demo 比單純問答更能證明 AI agent 的產品深度。

## 8. 我學到的事

**頂級客服 AI 的核心是判斷順序。** 先判斷是不是任務、再判斷資訊夠不夠、再決定查資料或追問。

**追問不是弱，是負責任。** 資訊不足時硬推薦會讓人覺得 AI 不懂；精準追問反而更像真人客服。

**Rerank 要理解場景。** 商務、聊天、慶生、家庭聚餐不是裝飾詞，它們會改變推薦排序。

**Web/LINE 的一致性在 contract，不在畫面。** UI 可以不同，底層 intent、state、cards、CTA 必須一致。

**世界級不是一次做到。** 它靠測試、真實截圖、使用者回饋和一輪輪回歸修正累積出來。

## English Version

# Case Study 13: AI Concierge Quality Hardening — From Answering to Reliable Service

ByteBites already had restaurant recommendation capability, but it was not yet strong enough as a customer-service agent. It sometimes treated clear restaurant requests as generic chat, failed to clarify vague group dining needs, or allowed noisy categories to outrank contextually better options.

The fix was a dialogue policy upgrade: detect clear dining intent first, extract constraints, run semantic search, apply hard cuisine/district filters, rerank by dining context, and only then produce a concise concierge response. For vague needs, the assistant now asks the smallest useful follow-up instead of pretending to know enough.

The most important product shift is that "business", "quiet chat", "group dining", and "family" are not decorative words. They change ranking. A top customer-service AI must know when to search, when to ask, and when to avoid overconfident answers.

The work is protected by regression tests around recommendation fallback, legacy seed removal, context handling, and clarification behavior. The lesson: world-class AI service quality is not only model fluency. It is routing, state, constraints, reranking, contract consistency, and measured regression control.
