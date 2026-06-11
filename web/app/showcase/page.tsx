import Link from "next/link";
import {
  ArrowRight,
  CalendarCheck,
  CarFront,
  CheckCircle2,
  CreditCard,
  DatabaseZap,
  MessageSquareText,
  MonitorPlay,
  Route,
  ShieldCheck,
  Sparkles,
  Store,
  Workflow,
} from "lucide-react";

const DEMO_STEPS = [
  {
    label: "1",
    title: "一句話說需求",
    body: "使用者在 LINE 或 Web 輸入地點、料理、人數與時間，AI 先收斂意圖，不急著亂推薦。",
    icon: MessageSquareText,
  },
  {
    label: "2",
    title: "回三張可行選項",
    body: "推薦卡不只顯示店名，也帶出區域、菜色、適合情境與下一步動作。",
    icon: Sparkles,
  },
  {
    label: "3",
    title: "對話產生訂位草稿",
    body: "AI 整理店家、日期、時間與人數，先讓使用者確認，避免直接誤訂。",
    icon: CalendarCheck,
  },
  {
    label: "4",
    title: "確認後才送出",
    body: "Web 與 LINE 都支援確認卡；使用者也能回「沒問題」用自然語送出。",
    icon: CheckCircle2,
  },
  {
    label: "5",
    title: "付款與候補同步",
    body: "訂金、付款狀態、額滿候補與取消會同步在 Web / LINE 的同一套狀態 contract。",
    icon: CreditCard,
  },
  {
    label: "6",
    title: "出發前停車提醒",
    body: "訂位者若會開車，系統在出發前整理附近停車空位，並提供展示用車位保留流程。",
    icon: CarFront,
  },
];

const ADVANTAGES = [
  {
    title: "不是餐廳搜尋，是用餐安排",
    body: "一般平台停在找店；ByteBites 把搜尋、訂位、付款、候補通知與停車提醒接成一條流程。",
    icon: Route,
  },
  {
    title: "AI 先確認，再執行",
    body: "高風險動作不靠猜。Web 與 LINE 都會產生訂位草稿，等使用者確認後才送出。",
    icon: ShieldCheck,
  },
  {
    title: "跨入口但同 contract",
    body: "LINE 和 Web UI 可以不同，但背後共享推薦、訂位、付款、取消與通知狀態。",
    icon: Workflow,
  },
  {
    title: "商家端也能展示價值",
    body: "商家後台可以管理時段容量，讓 AI 訂位不是單純聊天，而是能落到營運資料。",
    icon: Store,
  },
];

const TECH_POINTS = [
  "Java backend 管理訂位、付款、候補、停車與商家容量",
  "Python AI service 負責語意搜尋、LINE 對話、Web Agent 與狀態機",
  "Qdrant semantic search 搭配分類 hard constraints，降低不相關推薦",
  "RabbitMQ / notification flow 支援候補釋出與 LINE 主動通知",
  "Flyway migrations 保持資料演進可追蹤，legacy seed 已安全移除",
  "AI service 測試 120 passed，覆蓋 LINE / Web 對話與推薦回歸",
];

const METRICS = [
  { value: "500+", label: "commits", caption: "從資料、AI、LINE、付款到部署持續迭代" },
  { value: "120", label: "AI tests", caption: "LINE / Web 對話與推薦回歸測試" },
  { value: "2", label: "entry points", caption: "Web 與 LINE 雙入口同步體驗" },
  { value: "1", label: "journey", caption: "從選店到出發的完整用餐流程" },
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
      <p className="text-xs font-black tracking-normal text-emerald-700">{eyebrow}</p>
      <h2 className="mt-3 text-3xl font-black tracking-normal text-[#171512] md:text-5xl">{title}</h2>
      {description ? <p className="mt-4 text-base leading-8 text-zinc-600">{description}</p> : null}
    </div>
  );
}

function LineConversationMock() {
  return (
    <div className="rounded-[2rem] border border-zinc-200 bg-[#111312] p-4 shadow-2xl shadow-black/15">
      <div className="rounded-[1.5rem] bg-[#202322] p-4 text-sm text-white">
        <div className="mb-5 flex items-center gap-3 border-b border-white/10 pb-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-900 text-xl font-black">B</div>
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
          <p className="text-xs font-black text-emerald-700">BYTEBITES DRAFT</p>
          <p className="mt-1 text-xl font-black">確認訂位內容</p>
          <div className="mt-4 space-y-2 text-sm">
            <div className="flex justify-between gap-4 border-b border-zinc-100 pb-2">
              <span className="text-zinc-500">店家</span>
              <span className="font-bold">青田七六</span>
            </div>
            <div className="flex justify-between gap-4 border-b border-zinc-100 pb-2">
              <span className="text-zinc-500">時間</span>
              <span className="font-bold">明天 19:00</span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-zinc-500">人數</span>
              <span className="font-bold">4 人</span>
            </div>
          </div>
          <div className="mt-4 rounded-xl bg-emerald-700 px-4 py-3 text-center text-sm font-black text-white">
            確認送出訂位
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ShowcasePage() {
  return (
    <main className="min-h-screen bg-[#fbfaf6] text-[#171512]">
      <section className="border-b border-zinc-200 bg-[linear-gradient(180deg,#fffdf8_0%,#f4f8f5_100%)] px-5 py-14 md:px-10 md:py-20">
        <div className="mx-auto grid max-w-7xl gap-12 lg:grid-cols-[1fr_0.82fr] lg:items-center">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-white px-4 py-2 text-xs font-black text-emerald-800 shadow-sm">
              <MonitorPlay className="h-4 w-4" />
              Presentation Showcase
            </div>
            <h1 className="bb-display-serif mt-7 max-w-4xl text-5xl leading-[1.02] tracking-normal md:text-7xl">
              把用餐安排
              <span className="block text-emerald-700">交給 AI</span>
            </h1>
            <p className="mt-7 max-w-2xl text-lg leading-9 text-zinc-600 md:text-xl">
              ByteBites 不是只回答餐廳問題，而是把餐廳搜尋、訂位確認、付款狀態、候補通知與停車提醒整合成一個跨 Web / LINE 的 AI Dining Concierge。
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Link
                href="/ai?q=%E5%B9%AB%E6%88%91%E6%89%BE%E5%A4%A7%E5%AE%89%E5%8D%80%E9%81%A9%E5%90%88%E8%81%8A%E5%A4%A9%E8%81%9A%E9%A4%90%EF%BC%8C%E6%98%8E%E5%A4%A9%E6%99%9A%E4%B8%8A%207%20%E9%BB%9E%204%20%E4%BA%BA"
                className="inline-flex items-center justify-center gap-2 rounded-full bg-[#171512] px-5 py-3 text-sm font-black text-white transition hover:bg-black"
              >
                開始 AI Demo
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                href="/merchant"
                className="inline-flex items-center justify-center gap-2 rounded-full border border-zinc-300 bg-white px-5 py-3 text-sm font-black text-zinc-800 transition hover:border-emerald-400"
              >
                查看商家後台
              </Link>
            </div>
          </div>
          <LineConversationMock />
        </div>
      </section>

      <section className="border-b border-zinc-200 px-5 py-12 md:px-10">
        <div className="mx-auto grid max-w-7xl gap-3 md:grid-cols-4">
          {METRICS.map((metric) => (
            <div key={metric.label} className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
              <p className="font-mono text-4xl font-black text-[#171512]">{metric.value}</p>
              <p className="mt-1 text-sm font-black text-emerald-700">{metric.label}</p>
              <p className="mt-3 text-xs leading-5 text-zinc-500">{metric.caption}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="border-b border-zinc-200 px-5 py-16 md:px-10">
        <SectionHeading
          eyebrow="DEMO FLOW"
          title="上台就展示這 6 步"
          description="不要分散展示功能。照這條路線走，觀眾會看到一個完整產品，而不是幾個分開的小工具。"
        />
        <div className="mx-auto grid max-w-7xl gap-4 md:grid-cols-2 xl:grid-cols-3">
          {DEMO_STEPS.map((step) => {
            const Icon = step.icon;
            return (
              <div key={step.title} className="rounded-lg border border-zinc-200 bg-white p-6 shadow-sm">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-emerald-50 text-emerald-800">
                    <Icon className="h-5 w-5" />
                  </div>
                  <span className="font-mono text-sm font-black text-zinc-300">{step.label}</span>
                </div>
                <h3 className="mt-5 text-xl font-black tracking-normal">{step.title}</h3>
                <p className="mt-3 text-sm leading-7 text-zinc-600">{step.body}</p>
              </div>
            );
          })}
        </div>
      </section>

      <section className="border-b border-zinc-200 bg-[#f5f7f5] px-5 py-16 md:px-10">
        <SectionHeading
          eyebrow="WHY BYTEBITES"
          title="優勢要講成產品差異"
          description="你們的亮點不是 AI 會聊天，而是 AI 能把餐飲流程接起來，並且在高風險操作前先確認。"
        />
        <div className="mx-auto grid max-w-7xl gap-4 md:grid-cols-2">
          {ADVANTAGES.map((item) => {
            const Icon = item.icon;
            return (
              <div key={item.title} className="rounded-lg border border-zinc-200 bg-white p-6 shadow-sm">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#171512] text-white">
                    <Icon className="h-5 w-5" />
                  </div>
                  <h3 className="text-xl font-black tracking-normal">{item.title}</h3>
                </div>
                <p className="mt-4 text-sm leading-7 text-zinc-600">{item.body}</p>
              </div>
            );
          })}
        </div>
      </section>

      <section className="border-b border-zinc-200 px-5 py-16 md:px-10">
        <div className="mx-auto grid max-w-7xl gap-10 lg:grid-cols-[0.85fr_1fr] lg:items-start">
          <div>
            <p className="text-xs font-black tracking-normal text-emerald-700">ENGINEERING CREDIBILITY</p>
            <h2 className="mt-3 text-3xl font-black tracking-normal md:text-5xl">不只 demo，是可演進的系統</h2>
            <p className="mt-5 text-base leading-8 text-zinc-600">
              報告時要讓教授知道：你們有處理資料治理、AI 回歸、LINE/Web contract、訂位付款狀態和部署穩定性，不是只有畫面。
            </p>
          </div>
          <div className="grid gap-3">
            {TECH_POINTS.map((point) => (
              <div key={point} className="flex items-start gap-3 rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
                <DatabaseZap className="mt-0.5 h-5 w-5 shrink-0 text-emerald-700" />
                <p className="text-sm font-semibold leading-6 text-zinc-700">{point}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="px-5 py-16 md:px-10">
        <div className="mx-auto max-w-7xl">
          <div className="grid gap-6 rounded-lg border border-emerald-200 bg-emerald-900 p-6 text-white md:grid-cols-[1fr_auto] md:items-center md:p-8">
            <div>
              <p className="text-xs font-black tracking-normal text-emerald-200">ONE-LINE PITCH</p>
              <h2 className="mt-3 text-2xl font-black tracking-normal md:text-4xl">
                ByteBites 讓使用者不用想流程，只要說出需求，AI 就把用餐安排整理到可以執行。
              </h2>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row md:flex-col">
              <Link
                href="/ai"
                className="inline-flex items-center justify-center gap-2 rounded-full bg-white px-5 py-3 text-sm font-black text-emerald-950"
              >
                試用 AI
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                href="/"
                className="inline-flex items-center justify-center gap-2 rounded-full border border-white/30 px-5 py-3 text-sm font-black text-white"
              >
                回首頁
              </Link>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
