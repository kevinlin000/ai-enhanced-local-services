# ADR 0001：Java、Python AI、ETL 與 Web 的職責分離

## 狀態

已採納（Accepted）

## 背景

ByteBites 是台灣在地化的點評與訂位平台，包含 AI 輔助的餐廳探索。系統由四個部分組成：Java 後端、Python AI 服務、ETL 資料管線、Next.js 前端。

這個專案的價值在於同時展示 Java 後端能力與 AI 應用能力——兩者的責任邊界一旦模糊，兩邊都不成立。另一個現實約束是變更節奏：交易邏輯要求穩定（每次修改都要通過完整的合約測試），AI 排序需要高頻實驗（一天可能調整多次）。放在同一個 codebase 裡，兩種節奏會互相拖累。

## 決策

職責分離如下：

- **Java 後端**是業務資料與交易流程的唯一權威來源（source of truth）：訂位、付款、臨場事件、補款退款、商家容量。
- **Python AI 服務**擁有 RAG、語意搜尋、Agent 行為、guardrail 與 LINE 對話回應；需要業務狀態時一律回查 Java，不自行持有。
- **ETL 管線**負責餐廳資料品質與 Qdrant 向量索引同步。
- **Next.js 前端**負責消費者介面與商家後台；不保存權威狀態。

服務間通訊維持 HTTP REST。除非有明確理由重新評估，不引入 gRPC 或事件匯流排。

**不再細拆**：目前的複雜度核心是「訂位、付款、庫存、事件之間的交易一致性」，這是資料庫交易能直接解決的問題。過早拆成微服務會把它變成分散式交易、事件補償與重試成本——對這個規模是純粹的損失。

## 後果

- 不把 RAG 或 LLM 協調邏輯搬進 Java。
- 不讓 Python 成為訂位或付款狀態的來源。
- 跨服務變更必須同時驗證 API 合約與使用者可見行為。
- 設計目標的驗收標準：「Java 拿掉 AI 仍是合格的後端作品；Python 獨立拿出去仍是合格的 AI 作品」。

---

## English Summary

**Decision**: Keep four responsibilities separate — the Java backend is the single source of truth for business data and transactional workflows (booking, payment, incidents, refunds, capacity); the Python AI service owns RAG, semantic search, agent behavior, guardrails and LINE-facing responses, and always queries Java for business state; the ETL pipeline owns restaurant data quality and Qdrant payload sync; the Next.js frontend owns UI and holds no authoritative state. Communication stays HTTP REST.

**Why**: transactional logic and AI ranking evolve at different speeds; blending them hurts both. Splitting further into microservices would turn problems solvable by database transactions into distributed-transaction problems — a net loss at this scale.

**Consequences**: no LLM orchestration in Java, no booking/payment state in Python, cross-service changes must verify both contract and user-facing behavior. Acceptance bar: each side must stand alone as a portfolio-quality artifact.
