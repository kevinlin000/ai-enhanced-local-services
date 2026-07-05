# Case Study 15: AI 回答不穩定 — 從「越修越壞」到 eval 回歸防護網

**TL;DR** AI 推薦品質忽好忽壞，每修一個 case 就壞另一個。根因不是模型，是四層系統性問題：未設 temperature、對不存在分類的硬映射、無保底的嚴格過濾、以及**死掉的 eval**。修復後 Hit@5 從 66.7% 到 100%，更重要的是留下一套「改排序前必跑」的回歸防護網。

**Tech:** Gemini function calling / Qdrant / eval harness / AST-verified refactoring
**Repo:** `ai-service-python/app/ranking.py`, `ai-service-python/evals/`, `ai-service-python/app/guardrail.py`

## 1. 症狀：同一個問題，每次答案不一樣

「信義區火鍋」有時回三家火鍋，有時混進拉麵；「適合約會的鐵板燒」直接回空。
每次修復都是「加一個關鍵字特例」，牛排、漢堡、火鍋各自長出一套 hardcode
排序函式——修 A 壞 B，沒有人知道現在整體品質是好是壞。

## 2. 根因有四層，一層比一層深

1. **Temperature 未設定。** Agent 的 tool-calling 迴圈沒有傳 `temperature`，
   Gemini 預設 1.0——同一個問題每次走的工具路徑都可能不同。這是「不穩定」
   最大的單一來源，修復是一行：`temperature=0.2`。
2. **幽靈分類。** 查詢「高檔餐廳/鐵板燒」被映射到 `fine-dining` 分類——但資料庫
   12 個分類 slug 裡**根本沒有 fine-dining**。這個映射唯一的作用就是讓下一層
   過濾把所有結果殺光。
3. **嚴格過濾沒有保底。** 行政區與捷運站過濾都有「符合數不足就回補」的邏輯，
   唯獨分類過濾在零符合時直接覆蓋成空清單。「適合約會的鐵板燒」回空就是
   2 + 3 的組合技。
4. **Eval 是殭屍。** `evals/report.md` 停在一個半月前、Hit@5 = 0/10 ——
   dataset 裡的期望店家 ID 還是 73 家店時代的。沒有量測，所有排序修改
   都是賭博，這才是「越修越壞」的真正機制。

## 3. 修復順序：先復活量測，再動排序

先重建 gold dataset（600 家店的真實 ID、期望集 = 所有滿足 rationale 條件的店），
跑出基線 66.7%，然後每個修復都用 eval 驗證：

| 修復 | Hit@5 |
|---|---|
| 基線（dataset 修正後） | 10/15 |
| 拆掉 fine-dining 幽靈映射 + 分類過濾加保底 | 13/15 |
| buffet 視為用餐形式非菜系（和食吃到飽 = japanese）＋補「辣」「一人」意圖詞 | 15/15 |

輸出端同步修 guardrail：原本輸出只要含一個 blocklist 字眼就**整段換成道歉**——
使用者看到的就是「AI 突然壞掉」。改成句級遮蔽後，一個字眼不再毀掉整個回答。

## 4. 結構性收尾：讓下一次修改不再是賭博

排序層（69 個純函式、1,287 行）用 AST 閉包驗證後機械拆出 `ranking.py`，
與 IO 隔離。搭配兩條工作規則：

- 改 `ranking.py` 之前先跑 `evals/run_eval.py`，改完必須 ≥ 改前。
- 新的品質抱怨先變成 dataset case，再動 code。

## 5. 面試視角的重點

- 「AI 回答不穩定」的第一嫌疑人往往不是模型，是**工程參數與資料**
  （temperature、映射表、過濾邏輯）。
- Eval 不是加分項，是排序系統的 CI——沒有它，每個 hotfix 都在製造下一個 bug。
- 期望集要隨資料集演進：dataset 寫死在 73 家店時代，600 家店之後
  「正確答案」本身就變了。
