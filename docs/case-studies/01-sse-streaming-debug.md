# Case Study 01: AI Agent 真實串流 — 三層 debug 走完

**TL;DR** 做 ByteBites 的 AI 餐廳推薦對話時，我以為加了 SSE 就有串流體驗。實際打開瀏覽器發現：等 15 秒，文字突然全部出現。這篇記錄跟 Claude / Codex 三輪 debug，把 TTFT (time-to-first-token) 從「實質無限大」壓到 908ms 的過程。

**Tech:** Python / FastAPI / Gemini SDK / Server-Sent Events / Next.js  
**Repo:** `ai-service-python/app/main.py`

## 1. 我以為我做了串流

最初版本後端有 SSE endpoint，前端也有 reader，`text/event-stream` header 正確。功能上「會動」，但體感很慢。我一開始以為是 Gemini 本身慢。

直到 Codex audit 時用 `curl` 看 raw SSE timeline：

```text
thinking -> [3-15s silence] -> [all chunks burst in <200ms] -> done
```

那一刻才意識到：我做的是假串流。chunks 是 LLM 跑完之後才一次吐出來，跟「不做串流加 spinner」沒有本質差別。

## 2. 第一層：同步 SDK call 阻塞 async generator

原本 endpoint 形狀大概是：

```python
async def event_gen():
    yield _sse_frame({"type": "status", "message": "thinking"})
    final_answer = await _run_agent_turn(...)  # blocks for seconds
    for chunk in chunks(final_answer):
        yield _sse_frame({"type": "chunk", "content": chunk})
```

`_run_agent_turn` 內部呼叫 Gemini SDK 的同步 `generate_content`，完整 response ready 後才開始 yield chunks。

第一個修法：改用 `generate_content_stream`，把 agent turn 重構成 async generator，讓 Gemini 邊產生 token，後端邊 yield SSE。

跑一次 `curl`，第一個 chunk 還是沒出來。第一層修完，不代表串流真的可用。

## 3. 第二層：tool-call history 污染 synthesis context

加 log 後發現 Gemini stream 回的不是 text，而是 `function_call`。

Agent 流程：

1. 使用者問「推薦信義區火鍋」
2. Gemini 決定呼叫 `semantic_shop_search`
3. tool 結果被放回 `contents`
4. 同一包 `contents` 再餵給 `generate_content_stream` 做 synthesis

bug 在第 4 步。`contents` 裡有 function-call history，Gemini 看到後推斷下一輪也要 call tool，所以回另一個 function_call，而不是文字。沒有 text，就沒有 chunk。

這層是 Claude 提出的假設，我用 raw payload log 驗證。

修法：分離 tool-execution context 與 synthesis context。

```python
# Tool loop keeps full history for reasoning.
contents.append(candidate.content)
contents.append(Content(role="tool", parts=[Part.from_function_response(...)]))

# Synthesis uses clean plain-text context.
synthesis_contents = [
    Content(role="user", parts=[Part.from_text(
        f"使用者問：{query}\n\n查詢結果：\n{compact_tool_context}"
    )])
]
```

跑完這層，chunks 真的開始逐段出來。

## 4. 第三層：context 太大，prefill 吃掉 TTFT

串流是真的了，但 TTFT 還在 6 秒左右。

我量 synthesis prompt size：每家店餵完整 `ai_summary`、reviews、metadata，總共約 5KB、約 788 tokens。Gemini 要先讀完 input tokens 才能產生第一個 output token，input 越大，prefill 越慢。

修法：把 synthesis context 從完整 JSON 壓成每家店一行重點。

```text
# Before
{"shop_id": 10115, "name": "辛殿麻辣鍋", "ai_summary": "...", "reviews": [...]}

# After
辛殿麻辣鍋 | 信義 | 捷運象山 | $600+ | 麻辣湯頭濃郁 | 肉品海鮮吃到飽
```

token 減少約 70%。但實測 TTFT median 沒顯著改善。直覺上應該變快，數據上沒有。

結論：這層不是主要瓶頸。prefill 理論節省被 Gemini API latency variance 吃掉。

## 5. 第四層：換 model

意識到是 model latency floor 後，跑 model ablation：

| Model | TTFT | Quality | Tool routing |
|---|---:|---:|---|
| `gemini-3.5-flash` | 4.18s | 3/5 | OK |
| `gemini-3.1-flash-lite` | 2.28s, Qdrant warm 後 908ms | 4/5 | OK |
| `gemini-2.5-flash-lite` | 0.92s | 2/5 | failed hotpot routing |

Claude 一開始建議試 `2.5-flash-lite`，因為它偏低延遲。我 push back：為什麼不用同 tier 但較新的 `3.1-flash-lite`？最後兩個都測，數據證明 `2.5` 雖快但 routing 不穩，直接出局。

## 6. 最後數字

| Stage | TTFT | Total latency |
|---|---:|---:|
| Fake streaming | effectively infinite | 22.5s |
| Layer 1 + 2 | ~6s | ~12s |
| Context compression | ~6s | ~10s |
| Model swap | 908ms | ~8s |

TTFT 從實質無限大到 < 1 秒。total latency 從 22.5s 到約 8s。

## 7. 我學到的事

**「功能會動」不等於設計對。** SSE header 與 event format 都正確，但同步 SDK call 讓整個 async streaming 失效。

**root cause 常在不直觀的層。** 表面是「stream 沒輸出」，真正原因是 function-call history 讓模型繼續回 function_call。

**AI 協作要驗證。** Claude 提假設，Codex 跑 audit，我看 log 決定下一步。AI 給選項，工程師要驗證與取捨。

**量化比直覺重要。** token 壓縮看起來合理，但實測沒有降低 TTFT。沒有量化就會誤以為自己修好了。

## English Version

# Case Study 01: Real Streaming for an AI Agent — Three Layers of Debugging

**TL;DR** I built an SSE-based AI restaurant recommendation chat and assumed SSE meant streaming. In the browser: 15 seconds of silence, then the full answer appears at once. This case study covers the debugging process with Claude and Codex that moved TTFT from effectively infinite to 908ms.

The first version had the right endpoint, reader, and headers. But `curl` exposed the truth:

```text
thinking -> [3-15s silence] -> [all chunks burst in <200ms] -> done
```

The first bug was a synchronous Gemini SDK call inside an async generator. The endpoint yielded `thinking`, waited for the complete LLM response, then chunked the finished string.

The second bug was subtler: the synthesis call reused conversation history containing `function_call` and `function_response` parts. Gemini inferred it should call another tool instead of producing text, so the stream returned no text chunks. The fix was to keep full tool history for internal reasoning, but rebuild synthesis context as plain text: original query plus formatted tool result.

The third hypothesis was context bloat. I compressed the synthesis prompt from full JSON to one-line shop summaries, reducing tokens by about 70%. Measurement showed TTFT did not materially improve; model/API latency variance swallowed the theoretical prefill gain.

The real breakthrough was model selection. A small ablation showed `gemini-2.5-flash-lite` was fastest but failed tool routing, while `gemini-3.1-flash-lite` delivered the right balance of latency and reasoning. With Qdrant warm, TTFT reached 908ms.

**Lesson:** streaming is not a header; it is a timeline. Always inspect raw event arrival with `curl`. AI tools help generate hypotheses, but engineering judgment comes from logs, benchmarks, and trade-offs.
