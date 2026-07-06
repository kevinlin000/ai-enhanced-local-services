import Link from "next/link";
import {
  AlertTriangle,
  ArrowRight,
  Bell,
  CalendarDays,
  CheckCircle2,
  Compass,
  CreditCard,
  Heart,
  MessageSquareText,
  Sparkles,
  Store,
} from "lucide-react";

const demoQuery = "大安區 4 人適合聊天聚餐，明天晚上 7 點，可線上訂位";

const primaryLinks = [
  {
    title: "AI 推薦",
    body: "用自然語言說人數、地點、料理與時間，AI 會回覆結構化的推薦卡與理由。",
    href: `/ai?q=${encodeURIComponent(demoQuery)}`,
    cta: "打開 AI",
    icon: MessageSquareText,
  },
  {
    title: "探索餐廳",
    body: "599 家台北店家：分類、捷運區域、篩選與完整的餐廳詳情。",
    href: "/shops",
    cta: "看餐廳",
    icon: Compass,
  },
  {
    title: "我的訂位",
    body: "訂位、付款、改期、取消、停車偏好與臨場事件都集中在這裡管理。",
    href: "/my-bookings",
    cta: "看訂位",
    icon: CalendarDays,
  },
  {
    title: "商家後台",
    body: "店家視角：時段容量、臨場事件佇列、替代時段提案、押金與退款處理。",
    href: "/merchant",
    cta: "進後台",
    icon: Store,
  },
];

const workflow = [
  {
    title: "找店",
    body: "輸入「大安區 4 人適合聊天聚餐，明天晚上 7 點」，AI 會給出推薦理由與候選比較。",
    href: `/ai?q=${encodeURIComponent(demoQuery)}`,
    icon: MessageSquareText,
  },
  {
    title: "看懂店",
    body: "餐廳詳情整合介紹、真實評論、招牌菜、附近停車場與可訂時段。",
    href: "/shops/10102",
    icon: Compass,
  },
  {
    title: "訂位付款",
    body: "建立訂位後可查看 booking code、付款狀態、訂金與停車偏好。",
    href: "/my-bookings",
    icon: CreditCard,
  },
  {
    title: "臨場處理",
    body: "晚到或店家延遲會形成事件；商家提出替代時段，顧客決定接受或取消。",
    href: "/merchant",
    icon: AlertTriangle,
  },
  {
    title: "通知同步",
    body: "空位釋出、訂位更新、停車提醒與 LINE 上的操作，讀寫同一套後端狀態。",
    href: "/notifications",
    icon: Bell,
  },
  {
    title: "偏好回饋",
    body: "用餐後可記錄「太吵」「不再推薦」等偏好，之後的 AI 推薦會避開。",
    href: "/my-bookings",
    icon: Heart,
  },
];

const designPrinciples = [
  "Java 後端是訂位、付款、事件、押金與退款狀態的唯一來源。",
  "AI 服務負責理解需求、整理推薦、產生 LINE 與 Web 的操作卡。",
  "商家後台承接時段庫存、替代時段、退款 SLA 與升級處理。",
  "LINE 是操作入口：接受或拒絕都回到後端交易驗證，不在對話裡結案。",
  "599 家台北店家的照片、評論、介紹與情感分析全部對齊向量索引。",
];

function PageLink({
  href,
  children,
  variant = "secondary",
}: {
  href: string;
  children: React.ReactNode;
  variant?: "primary" | "secondary";
}) {
  const className =
    variant === "primary"
      ? "inline-flex min-h-10 items-center justify-center gap-2 rounded-lg bg-[#171512] px-4 py-2 text-sm font-semibold text-white transition hover:bg-black"
      : "inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-[#ded7c9] bg-[#fbfaf6] px-4 py-2 text-sm font-semibold text-[#3a352c] transition hover:bg-white";

  return (
    <Link href={href} className={className}>
      {children}
    </Link>
  );
}

export default function DemoPage() {
  return (
    <main className="bb-premium-page min-h-screen bg-[#f7f6f2] text-[#1c1914]">
      <div className="mx-auto flex max-w-[1500px] flex-col gap-5 px-4 py-5 lg:px-6">
        <section className="border border-[#ded7c9] bg-white">
          <div className="grid gap-5 p-5 lg:grid-cols-[1fr_420px]">
            <div>
              <p className="bb-page-kicker">Guided Tour</p>
              <h1 className="mt-2 text-3xl font-semibold tracking-normal">五分鐘看懂 ByteBites</h1>
              <p className="mt-3 max-w-3xl text-sm leading-6 text-zinc-600">
                這是一條完整的用餐營運流程：AI 找店、餐廳詳情、訂位付款、通知同步、商家後台。
                照下面的順序走，就能體驗從「說出需求」到「店家履約」的整條路。
              </p>
            </div>
            <div className="border border-[#ded7c9] bg-[#fbfaf6] p-4">
              <div className="flex items-start gap-3">
                <Sparkles className="mt-0.5 h-5 w-5 text-emerald-700" />
                <div>
                  <h2 className="text-base font-semibold tracking-normal">第一次來？</h2>
                  <p className="mt-1 text-sm leading-6 text-zinc-600">
                    從 AI 推薦開始，我們已經幫你準備好一句示範需求；用 LINE 登入可以體驗完整的訂位與通知。
                  </p>
                </div>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <PageLink href={`/ai?q=${encodeURIComponent(demoQuery)}`} variant="primary">
                  開始體驗
                  <ArrowRight className="h-4 w-4" />
                </PageLink>
                <PageLink href="/merchant">商家後台</PageLink>
              </div>
            </div>
          </div>
        </section>

        <section className="grid gap-5 xl:grid-cols-[360px_minmax(0,1fr)]">
          <aside className="border border-[#ded7c9] bg-white p-5">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold tracking-normal">四個入口</h2>
              <span className="rounded-lg bg-[#eee8dc] px-3 py-1 text-xs font-semibold text-[#5d5140]">
                消費端 × 商家端
              </span>
            </div>
            <div className="mt-4 space-y-3">
              {primaryLinks.map((item) => {
                const Icon = item.icon;
                return (
                  <Link
                    key={item.title}
                    href={item.href}
                    className="grid grid-cols-[40px_minmax(0,1fr)] gap-3 rounded-lg border border-[#ded7c9] bg-[#fffdf8] p-4 transition hover:border-[#b59a58] hover:bg-white"
                  >
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#eee8dc] text-[#3a352c]">
                      <Icon className="h-5 w-5" />
                    </div>
                    <div className="min-w-0">
                      <h3 className="text-base font-semibold tracking-normal">{item.title}</h3>
                      <p className="mt-1 text-sm leading-6 text-zinc-600">{item.body}</p>
                      <span className="mt-2 inline-flex items-center gap-2 text-sm font-semibold text-[#836d2e]">
                        {item.cta}
                        <ArrowRight className="h-4 w-4" />
                      </span>
                    </div>
                  </Link>
                );
              })}
            </div>
          </aside>

          <div className="space-y-5">
            <section className="border border-[#ded7c9] bg-white p-5">
              <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <div>
                  <p className="bb-page-kicker">The Journey</p>
                  <h2 className="mt-2 text-2xl font-semibold tracking-normal">一次用餐的完整旅程</h2>
                </div>
                <PageLink href="/merchant">
                  直接看商家後台
                  <Store className="h-4 w-4" />
                </PageLink>
              </div>
              <div className="mt-5 divide-y divide-[#ded7c9] border border-[#ded7c9]">
                {workflow.map((step, index) => {
                  const Icon = step.icon;
                  return (
                    <Link
                      key={step.title}
                      href={step.href}
                      className="grid gap-4 bg-[#fffdf8] p-4 transition hover:bg-white md:grid-cols-[56px_160px_minmax(0,1fr)_24px] md:items-center"
                    >
                      <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-[#eee8dc] text-[#3a352c]">
                        <Icon className="h-5 w-5" />
                      </div>
                      <div>
                        <p className="text-xs font-semibold text-[#b59a58]">Step {index + 1}</p>
                        <h3 className="mt-1 text-lg font-semibold tracking-normal">{step.title}</h3>
                      </div>
                      <p className="text-sm leading-6 text-zinc-600">{step.body}</p>
                      <ArrowRight className="hidden h-4 w-4 text-[#836d2e] md:block" />
                    </Link>
                  );
                })}
              </div>
            </section>

            <section className="grid gap-5 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1fr)]">
              <div className="border border-[#ded7c9] bg-white p-5">
                <p className="bb-page-kicker">Architecture</p>
                <h2 className="mt-2 text-2xl font-semibold tracking-normal">系統分工</h2>
                <p className="mt-3 text-sm leading-6 text-zinc-600">
                  AI 理解需求、Java 擁有交易狀態、LINE 與 Web 都只是操作入口。
                  介面可以不同，但每一筆訂位、付款與通知背後都是同一套後端狀態。
                </p>
                <div className="mt-5 flex flex-wrap gap-2">
                  <PageLink href="/shops/10102" variant="secondary">
                    <Compass className="h-4 w-4" />
                    餐廳詳情
                  </PageLink>
                  <PageLink href="/showcase">
                    <Sparkles className="h-4 w-4" />
                    專案亮點
                  </PageLink>
                </div>
              </div>
              <div className="border border-[#ded7c9] bg-white p-5">
                <h3 className="text-lg font-semibold tracking-normal">設計原則</h3>
                <ul className="mt-4 space-y-3">
                  {designPrinciples.map((point) => (
                    <li key={point} className="flex gap-3 text-sm leading-6 text-zinc-600">
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-700" />
                      <span>{point}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </section>
          </div>
        </section>
      </div>
    </main>
  );
}
