# Case Study 03: Model 選擇不是「越貴越好」— Agent ablation 拿到 8× 快、6× 便宜

**TL;DR** ByteBites AI 對話原本用 `gemini-3.5-flash`，TTFT 中位數約 7 秒，使用者等到不耐煩。我跑 3 模型 ablation，發現最快的 `2.5-flash-lite` 不是最適合的，最後選 `3.1-flash-lite`，TTFT 降到 908ms，token 成本降 6 倍。

**Tech:** Gemini models / async benchmarking / FastAPI Agent  
**Repo:** `ai-service-python/`

## 1. 問題：Agent 反應太慢

修完真實 SSE streaming 後，Agent TTFT 還是約 6 秒。使用者問「推薦信義區火鍋」，要等很久才看到第一個字。

我先以為是 context bloat，把 synthesis prompt 從約 5KB 壓到 1KB，token 砍 70%。結果 TTFT 沒明顯改善。這說明主要瓶頸不是 prefill，而是 model/API latency floor。

## 2. 候選 models

| Model | RPM | Design |
|---|---:|---|
| `gemini-3.5-flash` | 1K | baseline, quality-oriented |
| `gemini-3.1-flash-lite` | 4K | high throughput, newer lite generation |
| `gemini-2.5-flash-lite` | 4K | low latency |

Pro models 更慢且 quota 不適合互動式 Agent，排除。

## 3. 候選模型選擇的取捨

低延遲直覺會先指向 `2.5-flash-lite`，理由是它偏低延遲。但看完 tier list 後，這個判斷不完整：同樣 4K RPM，`3.1-flash-lite` 是較新世代，理論上推理與 tool routing 更穩。

因此真正要驗證的問題不是「哪個最快」，而是「哪個在 ByteBites 的 tool-routing workload 上最穩」。

最後決定不是聽誰的直覺，而是兩個都測。

## 4. Ablation 設計

3 models × 3 queries × 3 runs，取 median TTFT。queries 覆蓋三種 Agent 行為：

```text
Q1: 推薦信義區的火鍋              # semantic search + recommendation
Q2: 請幫我訂位明天晚上 7 點        # transaction intent
Q3: 鼎泰豐和饗饗哪個適合家庭聚餐    # comparison reasoning
```

每次 run 記錄：

- TTFT
- total latency
- quality rating
- tool routing correctness

## 5. 結果

| Model | TTFT median | Quality | Tool routing |
|---|---:|---:|---|
| `gemini-3.5-flash` | 4.18s | 3/5 | OK |
| `gemini-3.1-flash-lite` | 2.28s, Qdrant warm 後 908ms | 4/5 | OK |
| `gemini-2.5-flash-lite` | 0.92s | 2/5 | failed |

關鍵：`2.5-flash-lite` 雖最快，但在火鍋查詢上 routing 到 MRT search，1/3 query routing 失敗，直接出局。

`3.1-flash-lite` 不是單一指標最快，但 latency、quality、tool routing、cost 綜合最佳。

## 6. 成本也差 6 倍

| Model | Input | Output |
|---|---:|---:|
| `3.5-flash` | $1.50 / 1M tokens | $9.00 / 1M tokens |
| `3.1-flash-lite` | $0.25 / 1M tokens | $1.50 / 1M tokens |

對個人 project 來說成本差異看起來小，但 production scale 會放大。互動式 Agent 應該同時看 latency、quality、cost。

## 7. Env var 解耦

原本 model name hardcoded 在多個 call sites。改成 settings：

```python
class Settings(BaseSettings):
    gemini_agent_model: str = "gemini-3.1-flash-lite"
    gemini_chat_model: str = "gemini-3.5-flash"
```

Agent 與 ABSA 可以用不同 model：互動式對話用 fast/cheap，內容分析用 quality model。下一次 ablation 改 `.env` 就能跑，不用改 code。

## 8. 我學到的事

**低延遲直覺是 hypothesis，不是答案。** `2.5-flash-lite` 的方向有道理，但不能在未驗證 tool routing 前直接上線。

**task-specific benchmark 勝過 headline benchmark。** vendor 說 fastest，不代表適合你的 tool-routing agent。

**single metric winner 不一定是 production winner。** 2.5 latency 贏，但 quality 與 routing 輸。

**config 解耦很便宜，回報很大。** model swap 不該是 code change。

## English Version

# Case Study 03: Model Selection Is Not "More Expensive = Better"

ByteBites originally used `gemini-3.5-flash` for its AI Agent. Even after fixing true streaming, TTFT remained around 6-7 seconds. I first suspected prompt size, compressed context by about 70%, and measured no meaningful TTFT gain. The bottleneck was model/API latency, not token prefill.

The initial latency-first choice was `2.5-flash-lite`, but `3.1-flash-lite` was newer, in the same RPM tier, and likely to reason better. We tested both.

The ablation used 3 models × 3 queries × 3 runs and measured latency, quality, and tool routing. `2.5-flash-lite` was fastest but failed tool routing on hotpot queries. `3.1-flash-lite` gave the best production trade-off: fast enough, cheaper, and reliable routing.

The lesson: model selection must be task-specific. You do not pick the most expensive model, the newest model, or the lowest latency model. You pick the model that wins on your workload and your failure modes.
