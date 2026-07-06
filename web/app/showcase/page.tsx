import Link from "next/link";
import {
  ArrowRight,
  CalendarCheck,
  CarFront,
  CheckCircle2,
  Code2,
  CreditCard,
  MessageSquareText,
  Route,
  ShieldCheck,
  Sparkles,
  Store,
  Workflow,
} from "lucide-react";

const JOURNEY_STEPS = [
  {
    label: "1",
    title: "自然語言需求",
    body: "使用者在 Web 或 LINE 說出地點、料理、人數與時間。條件不足時，AI 會先追問收斂，而不是硬給結果。",
    icon: MessageSquareText,
  },
  {
    label: "2",
    title: "結構化推薦",
    body: "推薦卡帶出區域、菜色、適合情境與推薦理由；排序品質由版本化的檢索評估（Hit@5）持續把關。",
    icon: Sparkles,
  },
  {
    label: "3",
    title: "訂位草稿",
    body: "AI 從對話整理出店家、日期、時間與人數，先產生草稿讓使用者確認，不會直接替使用者下訂。",
    icon: CalendarCheck,
  },
  {
    label: "4",
    title: "確認後執行",
    body: "Web 與 LINE 都以確認卡送出；訂位建立、訂金與付款全部由 Java 後端的交易狀態機處理。",
    icon: CheckCircle2,
  },
  {
    label: "5",
    title: "狀態同步",
    body: "付款、額滿候補、改期與取消，在 Web 與 LINE 讀寫的是同一套後端狀態，不存在兩份真相。",
    icon: CreditCard,
  },
  {
    label: "6",
    title: "出發前提醒",
    body: "開車的訂位者會在出發前收到附近停車資訊與提醒，把服務範圍從「訂到位」延伸到「順利抵達」。",
    icon: CarFront,
  },
];

const BOUNDARIES = [
  {
    title: "完整旅程，不只搜尋",
    body: "多數平台停在找店。ByteBites 把搜尋、訂位、付款、候補通知與停車提醒接成同一條可執行的流程。",
    icon: Route,
  },
  {
    title: "高風險動作先確認",
    body: "訂位與付款不靠模型猜測。AI 只產生草稿，送出永遠發生在使用者明確確認之後。",
    icon: ShieldCheck,
  },
  {
    title: "雙入口、單一狀態",
    body: "LINE 與 Web 介面各自最佳化，但推薦、訂位、付款與通知共享同一套後端 contract。",
    icon: Workflow,
  },
  {
    title: "商家端閉環",
    body: "商家後台管理時段容量、臨場事件與退款，讓 AI 訂位落到真實營運資料，而不是聊天演示。",
    icon: Store,
  },
];

const ENGINEERING_FACTS = [
  "Java（Spring Boot 3 + JPA）擁有訂位、付款、候補、事件與退款的交易狀態機 — 115 個測試",
  "Python（FastAPI + Gemini function calling + Qdrant）負責語意檢索、對話 Agent 與 LINE 流程 — 191 個測試",
  "檢索品質有回歸防護網：版本化 gold dataset，Hit@5 15/15，改排序前後必跑",
  "Guardrail 雙向防護：輸入端擋 prompt injection，輸出端句級過濾而非整段封殺",
  "Prometheus 記錄每次 LLM 呼叫的 token 用量與延遲，Grafana dashboard 可視化",
  "AI 服務依依賴方向分層：config → ranking → retrieval → agent → line_routes",
];

const METRICS = [
  { value: "599", label: "台北店家", caption: "真實爬取資料：照片、評論、ABSA 情感分析與向量索引全對齊" },
  { value: "3,600", label: "店家照片", caption: "每店 6 張高解析總覽照，缺漏與重複皆為 0" },
  { value: "341", label: "自動化測試", caption: "Java 115 · Python 191 · Web 35，CI 全綠" },
  { value: "15/15", label: "檢索評估", caption: "Hit@5 回歸防護網，排序改動前後必跑" },
];

function SectionHeading({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string;
  title: string;
  description?: string;
}) {
  return (
    <div className="mx-auto mb-10 max-w-3xl text-center">
      <p className="bb-page-kicker">{eyebrow}</p>
      <h2 className="mt-3 text-3xl font-semibold tracking-normal text-[#171512] md:text-4xl">{title}</h2>
      {description ? <p className="mt-4 text-base leading-8 text-zinc-600">{description}</p> : null}
    </div>
  );
}

function LineConversationMock() {
  return (
    <div className="rounded-[2rem] border border-zinc-200 bg-[#111312] p-4 shadow-2xl shadow-black/15">
      <div className="rounded-[1.5rem] bg-[#202322] p-4 text-sm text-white">
        <div className="mb-5 flex items-center gap-3 border-b border-white/10 pb-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-900 text-xl font-semibold">B</div>
          <div>
            <p className="font-semibold">ByteBites</p>
            <p className="text-xs text-white/45">AI Dining Concierge</p>
          </div>
        </div>
        <div className="ml-auto max-w-[82%] rounded-2xl rounded-br-sm bg-[#59d56b] px-4 py-3 text-[#102614]">
          幫我找大安區適合聊天聚餐，明天晚上 7 點 4 人
        </div>
        <div className="mt-4 max-w-[88%] rounded-2xl rounded-bl-sm bg-white/14 px-4 py-3 text-white/86">
          我先整理 3 間適合聊天且可安排訂位的餐廳。
        </div>
        <div className="mt-4 rounded-2xl bg-white p-4 text-[#171512]">
          <p className="text-xs font-semibold text-emerald-700">BYTEBITES DRAFT</p>
          <p className="mt-1 text-xl font-semibold">確認訂位內容</p>
          <div className="mt-4 space-y-2 text-sm">
            <div className="flex justify-between gap-4 border-b border-zinc-100 pb-2">
              <span className="text-zinc-500">店家</span>
              <span className="font-semibold">青田七六</span>
            </div>
            <div className="flex justify-between gap-4 border-b border-zinc-100 pb-2">
              <span className="text-zinc-500">時間</span>
              <span className="font-semibold">明天 19:00</span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-zinc-500">人數</span>
              <span className="font-semibold">4 人</span>
            </div>
          </div>
          <div className="mt-4 rounded-xl bg-emerald-700 px-4 py-3 text-center text-sm font-semibold text-white">
            確認送出訂位
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ShowcasePage() {
  return (
    <main className="bb-premium-page min-h-screen text-[#171512]">
      <section className="border-b border-[rgb(222_216_203_/_0.82)] px-5 py-14 md:px-10 md:py-20">
        <div className="mx-auto grid max-w-7xl gap-12 lg:grid-cols-[1fr_0.82fr] lg:items-center">
          <div>
            <p className="bb-page-kicker">Engineering Overview</p>
            <h1 className="bb-display-serif mt-6 max-w-4xl text-5xl leading-[1.05] tracking-normal md:text-6xl">
              從一句話需求，
              <span className="block text-emerald-800">到可執行的用餐安排</span>
            </h1>
            <p className="mt-7 max-w-2xl text-lg leading-9 text-zinc-600">
              ByteBites 由三個服務組成：Java 後端擁有交易狀態、Python AI 服務負責理解與推薦、
              Next.js 與 LINE 提供雙入口。這一頁整理系統的運作方式與工程實證。
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Link
                href="/ai?q=%E5%B9%AB%E6%88%91%E6%89%BE%E5%A4%A7%E5%AE%89%E5%8D%80%E9%81%A9%E5%90%88%E8%81%8A%E5%A4%A9%E8%81%9A%E9%A4%90%EF%BC%8C%E6%98%8E%E5%A4%A9%E6%99%9A%E4%B8%8A%207%20%E9%BB%9E%204%20%E4%BA%BA"
                className="inline-flex items-center justify-center gap-2 rounded-lg bg-[var(--bb-forest)] px-5 py-3 text-sm font-semibold text-white transition hover:bg-emerald-900"
              >
                實際試一次 AI 訂位
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                href="https://github.com/kevinlin000/ai-enhanced-local-services"
                className="inline-flex items-center justify-center gap-2 rounded-lg border border-[rgb(167_137_67_/_0.28)] bg-[rgb(255_253_248_/_0.72)] px-5 py-3 text-sm font-semibold text-zinc-800 transition hover:bg-white"
              >
                <Code2 className="h-4 w-4" />
                原始碼與工程文件
              </Link>
            </div>
          </div>
          <LineConversationMock />
        </div>
      </section>

      <section className="border-b border-[rgb(222_216_203_/_0.82)] px-5 py-12 md:px-10">
        <div className="mx-auto grid max-w-7xl gap-3 md:grid-cols-4">
          {METRICS.map((metric) => (
            <div key={metric.label} className="bb-premium-surface rounded-lg p-5">
              <p className="font-mono text-4xl font-semibold text-[#171512]">{metric.value}</p>
              <p className="mt-1 text-sm font-semibold text-emerald-800">{metric.label}</p>
              <p className="mt-3 text-xs leading-5 text-zinc-500">{metric.caption}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="border-b border-[rgb(222_216_203_/_0.82)] px-5 py-16 md:px-10">
        <SectionHeading
          eyebrow="How it works"
          title="一次訂位在系統裡的六個階段"
          description="每個階段都能在這個網站與 LINE 上實際操作；下方每張卡描述的是系統行為，不是概念圖。"
        />
        <div className="mx-auto grid max-w-7xl gap-4 md:grid-cols-2 xl:grid-cols-3">
          {JOURNEY_STEPS.map((step) => {
            const Icon = step.icon;
            return (
              <div key={step.title} className="bb-premium-surface rounded-lg p-6">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-emerald-50 text-emerald-800">
                    <Icon className="h-5 w-5" />
                  </div>
                  <span className="font-mono text-sm font-semibold text-zinc-300">{step.label}</span>
                </div>
                <h3 className="mt-5 text-xl font-semibold tracking-normal">{step.title}</h3>
                <p className="mt-3 text-sm leading-7 text-zinc-600">{step.body}</p>
              </div>
            );
          })}
        </div>
      </section>

      <section className="border-b border-[rgb(222_216_203_/_0.82)] bg-[rgb(245_247_245_/_0.6)] px-5 py-16 md:px-10">
        <SectionHeading
          eyebrow="Design decisions"
          title="四條刻意畫出的邊界"
          description="這些不是功能列表，是系統設計時做出的取捨。"
        />
        <div className="mx-auto grid max-w-7xl gap-4 md:grid-cols-2">
          {BOUNDARIES.map((item) => {
            const Icon = item.icon;
            return (
              <div key={item.title} className="bb-premium-surface rounded-lg p-6">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#171512] text-white">
                    <Icon className="h-5 w-5" />
                  </div>
                  <h3 className="text-xl font-semibold tracking-normal">{item.title}</h3>
                </div>
                <p className="mt-4 text-sm leading-7 text-zinc-600">{item.body}</p>
              </div>
            );
          })}
        </div>
      </section>

      <section className="border-b border-[rgb(222_216_203_/_0.82)] px-5 py-16 md:px-10">
        <div className="mx-auto grid max-w-7xl gap-10 lg:grid-cols-[0.85fr_1fr] lg:items-start">
          <div>
            <p className="bb-page-kicker">Engineering evidence</p>
            <h2 className="mt-3 text-3xl font-semibold tracking-normal md:text-4xl">可驗證的工程實證</h2>
            <p className="mt-5 text-base leading-8 text-zinc-600">
              以下每一項都對應 repo 裡可執行的測試、評估報告或模組；
              完整的架構決策（ADR）與工程案例（case studies）收錄在原始碼的 docs 目錄。
            </p>
            <Link
              href="https://github.com/kevinlin000/ai-enhanced-local-services/tree/main/docs/case-studies"
              className="mt-6 inline-flex items-center gap-2 text-sm font-semibold text-emerald-800 hover:text-emerald-700"
            >
              閱讀工程案例
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
          <div className="grid gap-3">
            {ENGINEERING_FACTS.map((point) => (
              <div key={point} className="bb-premium-surface flex items-start gap-3 rounded-lg p-4">
                <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-700" />
                <p className="text-sm font-medium leading-6 text-zinc-700">{point}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="px-5 py-16 md:px-10">
        <div className="mx-auto max-w-7xl">
          <div className="grid gap-6 rounded-lg border border-emerald-200 bg-emerald-900 p-6 text-white md:grid-cols-[1fr_auto] md:items-center md:p-8">
            <div>
              <p className="text-xs font-semibold tracking-normal text-emerald-200">ByteBites</p>
              <h2 className="mt-3 text-2xl font-semibold tracking-normal md:text-3xl">
                說出需求，其餘的搜尋、確認、訂位與提醒交給系統。
              </h2>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row md:flex-col">
              <Link
                href="/ai"
                className="inline-flex items-center justify-center gap-2 rounded-lg bg-white px-5 py-3 text-sm font-semibold text-emerald-950"
              >
                開始對話
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                href="/demo"
                className="inline-flex items-center justify-center gap-2 rounded-lg border border-white/30 px-5 py-3 text-sm font-semibold text-white"
              >
                功能導覽
              </Link>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
