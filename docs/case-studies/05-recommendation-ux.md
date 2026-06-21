# Case Study 05: 推薦卡 UX — 從「暴露 ABSA」到「正面 framing」

**TL;DR** 我幫 ByteBites AI 推薦做了 ABSA aspect bar，原本以為這是技術透明。但截圖一看，推薦卡上寫「服務評價分歧」直接打臉自己的推薦。最後我移除 raw ABSA bar，改成正面 highlight，完整 ABSA 留在詳情頁。

**Tech:** Next.js / React / Tailwind / ABSA data  
**Repo:** `web/components/AgentShopCard.tsx`

## 1. 起點：我以為 ABSA bar 是差異化

ByteBites 對標 inline.app。inline 有照片、評論、地圖，但沒有 aspect-level sentiment。我有 ABSA pipeline，覺得推薦卡 show 4 軸 sentiment 會更強：

```text
AI 評論分析
菜色  mixed
服務  mixed
環境  mixed
價格  negative
```

技術上資料真實，pipeline 有 F1 0.955，但 UX 不一定對。

## 2. 打開截圖後翻車

我跑「推薦信義區火鍋」，第一張卡推薦辛殿麻辣鍋，但底下四個 aspect 都顯示 mixed。

使用者反應會是：你推薦這家，但你又告訴我它評價分歧，那為什麼推薦？

這不是 label wording 問題，而是 context 問題。推薦卡不是 review audit report。

## 3. 產品語境轉折

一開始很容易把問題看成 label wording：「褒貶」是不是該改成「中等」或「評價不一」？

但這不夠深。

我 push：「一般使用者看到推薦卡上都是分歧、負面，還會想去吃嗎？」

真正的本質是：ByteBites 的承諾是「我幫你選」，但 raw ABSA bar 在做「我把負評攤給你」。兩者互相打架。

## 4. Recommendation 和 Detail 是兩種 context

| Context | What belongs there |
|---|---|
| Recommendation card | positive framing, why this shop, CTA |
| Detail page | full reviews, positive and negative, transparent evidence |

推薦本身就是 opinionated curation。你已經替使用者篩選，推薦頁應該說明「為什麼選這家」，不是把所有判斷材料攤開讓使用者自己想。

## 5. 新設計：推薦卡只 show「為什麼推薦」

新 AgentShopCard：

- 左欄：照片、地點、價格、CTA
- 中欄：精選評論 carousel
- 右欄：Google Maps iframe
- 底部：1-2 個正面 highlight

```tsx
const items = aspects
  .filter((a) => {
    const posCount = (a.positive_evidence ?? []).length;
    const negCount = (a.negative_evidence ?? []).length;
    return a.sentiment === "positive" || (a.sentiment === "mixed" && posCount > negCount);
  })
  .slice(0, 2);
```

規則：

- 只 show positive-only highlights
- 不 fake highlight；沒有 clear positive 就不顯示
- 不在推薦卡 show negative/mixed warning
- full ABSA 保留在 shop detail

## 6. 這樣誠實嗎？

這不是隱藏負評，因為詳情頁仍然完整保留。推薦卡與詳情頁的責任不同。

真正不誠實的是：推薦一間店，同時在推薦卡上暗示你不要去。那不是透明，是推卸推薦責任。

好的產品分層應該是：

1. 推薦頁：做出判斷，給出理由
2. 詳情頁：提供完整資料，讓使用者深挖

## 7. Bonus：文字和卡片數量一致

修 ABSA card 時又發現另一個 bug：

- Agent 文字介紹 2 家
- frontend 卡片 render 3 家

原因：Agent narrative 和 frontend cards 是兩條資料流。文字由 LLM 自由生成，卡片由 `tool_result.shops.slice(0, 3)` 產生。

修法：Agent done event 輸出結構化決策：

```json
{
  "recommended_shop_ids": [10115, 10102],
  "narrative": "為您整理了 2 間符合的選擇...",
  "rejected_shop_ids": [10109],
  "rejection_summary": "排除非主類別店家"
}
```

Frontend 改成：

```tsx
const cards = recommended_shop_ids.map((id) =>
  toolResult.shops.find((shop) => shop.shop_id === id)
);
```

Agent 推幾家，文字講幾家，卡片 render 幾家。single source of truth。

## 8. 結果

「信義區想吃火鍋」：

- text 介紹 3 家
- cards render 3 家
- no orphan card
- no negative label on recommendation cards

「推薦大安區美式漢堡」：

- DB 只有 1 家合適
- text 1 家
- card 1 家
- narrative confident，附上擴大範圍建議

## 9. 我學到的事

**技術上正確，不等於產品上正確。** ABSA bar 真的、準確，但放錯 context。

**推薦頁與詳情頁要不同 framing。** 推薦頁 confident，詳情頁 transparent。

**把資料都丟給使用者是工程師思維。** 推薦產品要承擔選擇責任。

**single source of truth 是 UX 基礎。** narrative count 和 card count 不一致就是 bug。

**第一個修法常停在表面。** 改 label 不能解決推薦卡的語境問題，必須回到使用者看到畫面時的決策心理。

## English Version

# Case Study 05: Recommendation Card UX — From Exposing ABSA to Positive Framing

I initially added ABSA aspect bars to recommendation cards because the data was technically strong. It felt like a differentiator: inline-style cards plus aspect-level review intelligence.

But once I looked at the screenshots as a user, the product broke. A recommendation card that says "service mixed" or "price negative" undermines its own recommendation.

The issue was not wording. It was context. Recommendation cards and detail pages have different responsibilities. A recommendation card should explain why the system picked this shop. A detail page should expose complete evidence, including negative reviews.

The fix was to remove raw ABSA bars from recommendation cards and replace them with positive-only highlights derived from ABSA evidence. Full ABSA stays available on shop detail pages.

I also fixed a deeper consistency bug: cards were rendered from `tool_result.shops.slice(0, 3)` while narrative was generated separately by the Agent. The Agent now emits `recommended_shop_ids`, and the frontend renders cards from those IDs. Narrative count and card count now share one source of truth.

The lesson: product correctness is different from data correctness. Accurate data can still be wrong for the moment. Senior engineering means knowing not only how to build a feature, but whether that feature belongs in the user's current context.
