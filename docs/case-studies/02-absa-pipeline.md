# Case Study 02: ABSA 評論分析 Pipeline — 從規則模板做到 LLM, F1 0.955

**TL;DR** ByteBites 早期的「評論摘要」是 regex 模板拼出來的，六家店共用同一個骨架，輸出幾乎一樣。我換成 LLM-based ABSA (Aspect-Based Sentiment Analysis)，用 35 題手標 gold set 量到 F1 0.955。這篇記錄 pipeline 設計、雙層 faithfulness verifier，以及 103 家店 batch 時遇到的 data quality 問題。

**Tech:** Python / Gemini / Gemini Embedding / asyncio / MySQL JSON column  
**Repo:** `ai-service-python/`

## 1. 起點：模板式假摘要

早期摘要 generator 是模板：

```text
這家 {category} 餐廳位於 {area}，以 {top_tag} 聞名，
適合 {occasion}，評價 {rating_label}。
```

便宜、快、可預測，但沒有真正的店家特色。不同店輸出長得一樣，「評論摘要」名存實亡。

真正的 ABSA 要抽 aspect-level sentiment，例如：

- 菜色：皮蛋豆腐餃多人讚賞
- 服務：桌邊服務貼心
- 環境：空調過冷
- 價格：性價比受肯定

## 2. ABSA prompt 設計

跟 Claude 討論後，我先固定 4 個 aspect：菜色、服務、環境、價格。每個 aspect 要輸出正負 evidence、具體詞與來源評論。

```json
{
  "aspect": "dishes",
  "positive_evidence": [
    {
      "claim": "皮蛋豆腐餃受到稱讚",
      "source_review_ids": [12, 47],
      "concrete_terms": ["皮蛋豆腐餃"]
    }
  ],
  "negative_evidence": [],
  "sentiment": "positive",
  "confidence": "high"
}
```

關鍵設計：evidence 必須可溯源。`source_review_ids` 不是裝飾，而是 verifier 能工作的前提。

## 3. 雙層 faithfulness verifier

LLM evidence 最大風險是 hallucination。證據聽起來合理，不代表評論真的寫過。

### Layer 1: 字元比對

先用最便宜的方式：substring match。

```python
def char_match(evidence: str, review_text: str) -> bool:
    return evidence in review_text
```

35 題 gold set 上，char hit rate 約 0.795。20% evidence 字面找不到。

但 char miss 不一定是錯。很多是改寫：

- 評論：「鼎泰豐級的小籠包」
- evidence：「小籠包品質高」

字面 miss，語意 match。

### Layer 2: 語意 fallback

對 char miss 的 evidence，再做 embedding similarity。

```python
async def semantic_verify(evidence: str, review_sentences: list[str]) -> float:
    ev_vec = await embed(evidence)
    sent_vecs = await embed_batch(review_sentences)
    return max(cosine_similarity(ev_vec, sv) for sv in sent_vecs)
```

threshold sweep 後，0.80 是最穩的 cutoff：

| Cosine threshold | False positive | Correct recovery |
|---:|---:|---:|
| 0.90 | 0% | 32% |
| 0.80 | 2% | 78% |
| 0.70 | 8% | 89% |
| 0.60 | 22% | 94% |

實際 distribution 接近雙峰：同義改寫多在 0.80 以上，hallucination 多在 0.50 以下。

## 4. Gold set 結果

| Metric | Layer 1 only | Layer 1 + 2 |
|---|---:|---:|
| Hit rate | 0.795 | 0.998 |
| F1 | 0.810 | 0.955 |

雙層 verifier 把 false negative 救回來，F1 從 0.81 拉到 0.955。

## 5. 103 家 batch 遇到的問題

### 問題 1：Stage 2 跟 Stage 1 搶 quota

ABSA generation 用 chat model，semantic verifier 用 embedding model。改 async parallel 後，兩個 stage 搶 quota，很快遇到 429。

修法：拆成兩個 batch job。Stage 1 先寫 DB，只存 char hit rate；Stage 2 之後跑 semantic verifier，再回寫 semantic hit rate。

### 問題 2：dedup 露餡

54 家店 ABSA quality 偏低。檢查 raw review 發現 scraper 跑過兩次，重複評論讓 LLM evidence 偏向重複內容。

寫 dedup script 後清掉 180 row，affected shops 的 char hit rate 平均從 0.903 升到 0.935。

教訓：data quality 問題會偽裝成 model quality 問題。

### 問題 3：spec 本身錯了

taxonomy spot check 時發現「小品雅廚」被歸成素食，但評論有「紅燒蹄髈必點」。Classifier 100% 符合 spec，但 spec 本身錯。

修法：加入 Google Places `primary_type` 作為第三方 anchor。validator 不能跟被 validated 的 spec 來自同一份資料。

## 6. Production 數字

| Item | Value |
|---|---:|
| Gold set | 35 items |
| F1 | 0.955 |
| Production scale | 103 shops |
| Post-dedup char hit rate | avg 0.935 |
| Semantic recoveries | 132 evidence items |
| Cost per shop | about $0.001 |

## 7. 我學到的事

**LLM evaluation 不能只看感覺。** 35 題 gold set 看起來小，但足夠抓 systematic bias。

**雙層 verifier 比單層穩。** char match 抓 literal，semantic match 抓 paraphrase。

**先修 data，再修 prompt。** dedup 前做 prompt engineering 只是在錯資料上調參。

**校驗者不能等於被校驗者。** classifier 對 spec 100% 一致，不代表 spec 正確。

## English Version

# Case Study 02: ABSA Review Analysis Pipeline — From Templates to LLM, F1 0.955

ByteBites originally used regex templates for shop summaries. They were cheap and predictable, but every restaurant sounded the same. I replaced this with LLM-based ABSA, extracting aspect-level sentiment for food, service, environment, and price.

The key design was traceability. Each evidence item carries source review IDs and concrete terms, so it can be verified. I built a two-layer verifier:

1. character substring match
2. embedding-based semantic fallback for paraphrases

Character matching alone was too strict: many valid paraphrases failed literal matching. Semantic verification recovered those false negatives. On a 35-item hand-labeled gold set, F1 improved from 0.81 to 0.955.

Running the pipeline on 103 shops surfaced production issues: quota contention between chat and embedding stages, duplicated scraper reviews hurting metrics, and a taxonomy spec bug that only a third-party Google Places anchor could catch.

The core lesson: LLM quality is not just prompt quality. It is prompt design, verifier design, data quality, and independent validation.
