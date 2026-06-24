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
  RefreshCw,
  Store,
} from "lucide-react";

const demoQuery = "大安區 4 人適合聊天聚餐，明天晚上 7 點，可線上訂位";

const primaryLinks = [
  {
    title: "AI 推薦",
    body: "用自然語言說人數、地點、料理與時間，讓 AI 回結構化推薦卡。",
    href: `/ai?q=${encodeURIComponent(demoQuery)}`,
    cta: "打開 AI",
    icon: MessageSquareText,
  },
  {
    title: "探索餐廳",
    body: "看 599 家台北店、分類、捷運區域、篩選與餐廳詳情。",
    href: "/shops",
    cta: "看餐廳",
    icon: Compass,
  },
  {
    title: "我的訂位",
    body: "檢查訂位、付款、改期、取消、停車偏好與臨場事件。",
    href: "/my-bookings",
    cta: "看訂位",
    icon: CalendarDays,
  },
  {
    title: "商家後台",
    body: "看店家時段、incident queue、替代時段提案、押金與退款處理。",
    href: "/merchant",
    cta: "進後台",
    icon: Store,
  },
];

const workflow = [
  {
    title: "找店",
    body: "輸入「大安區 4 人適合聊天聚餐，明天晚上 7 點」，看 AI 推薦理由與比較表。",
    href: `/ai?q=${encodeURIComponent(demoQuery)}`,
    icon: MessageSquareText,
  },
  {
    title: "看懂店",
    body: "進餐廳詳情，看介紹、評論、特色、附近停車與可訂時段。",
    href: "/shops/10102",
    icon: Compass,
  },
  {
    title: "訂位付款",
    body: "建立訂位後，到我的訂位確認 booking code、付款狀態、訂金與停車偏好。",
    href: "/my-bookings",
    icon: CreditCard,
  },
  {
    title: "臨場處理",
    body: "晚到或店家延遲會形成 incident；商家提出替代時段，顧客接受或拒絕。",
    href: "/merchant",
    icon: AlertTriangle,
  },
  {
    title: "通知同步",
    body: "空位釋出、訂位更新、停車提醒與 LINE action 走同一套後端狀態。",
    href: "/notifications",
    icon: Bell,
  },
  {
    title: "偏好回饋",
    body: "訂位後可記錄太吵、不再推薦等偏好，後續 AI 推薦會避開。",
    href: "/my-bookings",
    icon: Heart,
  },
];

const proofPoints = [
  "Java backend 是訂位、付款、incident、押金與退款狀態來源。",
  "AI service 只負責理解需求、整理推薦、產生 LINE/Web 操作卡。",
  "商家後台能處理時段庫存、替代時段、退款 SLA 與 escalation。",
  "LINE 是 action channel，接受/拒絕仍回到 Java transaction 驗證。",
  "資料已恢復成 599 家台北 active shops，照片、評論、介紹與 ABSA 對齊。",
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
    <main className="bb-premium-page min-h-screen bg-[#f6f1e8] text-[#1c1914]">
      <section className="border-b border-[#ded7c9] px-6 py-10 md:px-12">
        <div className="mx-auto max-w-7xl">
          <p className="bb-page-kicker">Demo Guide</p>
          <div className="mt-3 grid gap-6 lg:grid-cols-[minmax(0,0.9fr)_minmax(320px,0.5fr)] lg:items-end">
            <div>
              <h1 className="text-4xl font-semibold tracking-normal md:text-6xl">錄影照這條路線走</h1>
              <p className="mt-4 max-w-3xl text-base leading-8 text-zinc-600">
                ByteBites 的重點不是首頁，而是從 AI 找店一路接到訂位、付款、LINE 通知、商家處理與退款營運。這頁把入口集中起來。
              </p>
            </div>
            <div className="rounded-lg border border-[#ded7c9] bg-[#fffdf8] p-5">
              <div className="flex items-start gap-3">
                <CheckCircle2 className="mt-0.5 h-5 w-5 text-emerald-700" />
                <div>
                  <h2 className="text-lg font-semibold tracking-normal">目前建議先展示</h2>
                  <p className="mt-2 text-sm leading-6 text-zinc-600">
                    AI 推薦、我的訂位、商家後台。LINE push 要用真 LINE 身份再測。
                  </p>
                </div>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <PageLink href={`/ai?q=${encodeURIComponent(demoQuery)}`} variant="primary">
                  開始展示
                  <ArrowRight className="h-4 w-4" />
                </PageLink>
                <PageLink href="/showcase">專案亮點</PageLink>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="border-b border-[#ded7c9] px-6 py-8 md:px-12">
        <div className="mx-auto grid max-w-7xl gap-4 md:grid-cols-2 xl:grid-cols-4">
          {primaryLinks.map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.title}
                href={item.href}
                className="group flex min-h-[190px] flex-col rounded-lg border border-[#ded7c9] bg-[#fffdf8] p-5 transition hover:border-[#b59a58] hover:bg-white"
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#eee8dc] text-[#3a352c]">
                  <Icon className="h-5 w-5" />
                </div>
                <h2 className="mt-5 text-xl font-semibold tracking-normal">{item.title}</h2>
                <p className="mt-2 flex-1 text-sm leading-6 text-zinc-600">{item.body}</p>
                <span className="mt-4 inline-flex items-center gap-2 text-sm font-semibold text-[#836d2e]">
                  {item.cta}
                  <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
                </span>
              </Link>
            );
          })}
        </div>
      </section>

      <section className="border-b border-[#ded7c9] px-6 py-10 md:px-12">
        <div className="mx-auto max-w-7xl">
          <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="bb-page-kicker">Recording Flow</p>
              <h2 className="mt-2 text-3xl font-semibold tracking-normal md:text-4xl">5 分鐘展示順序</h2>
            </div>
            <PageLink href="/merchant">
              直接看商家後台
              <Store className="h-4 w-4" />
            </PageLink>
          </div>
          <div className="mt-6 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {workflow.map((step, index) => {
              const Icon = step.icon;
              return (
                <Link
                  key={step.title}
                  href={step.href}
                  className="grid grid-cols-[44px_minmax(0,1fr)] gap-4 rounded-lg border border-[#ded7c9] bg-[#fffdf8] p-5 transition hover:border-[#b59a58] hover:bg-white"
                >
                  <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-[#eee8dc] text-[#3a352c]">
                    <Icon className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-[#b59a58]">Step {index + 1}</p>
                    <h3 className="mt-1 text-lg font-semibold tracking-normal">{step.title}</h3>
                    <p className="mt-2 text-sm leading-6 text-zinc-600">{step.body}</p>
                  </div>
                </Link>
              );
            })}
          </div>
        </div>
      </section>

      <section className="px-6 py-10 md:px-12">
        <div className="mx-auto grid max-w-7xl gap-6 lg:grid-cols-[0.8fr_1fr]">
          <div>
            <p className="bb-page-kicker">Talk Track</p>
            <h2 className="mt-2 text-3xl font-semibold tracking-normal md:text-4xl">你要講的不是「我做了很多頁」</h2>
            <p className="mt-4 text-base leading-8 text-zinc-600">
              講法要收斂成：AI 理解需求，Java 擁有交易狀態，LINE 和 Web 都只是入口。這樣面試官才會看到工程邊界。
            </p>
            <div className="mt-5 flex flex-wrap gap-2">
              <PageLink href="/shops/10102" variant="secondary">
                <Compass className="h-4 w-4" />
                餐廳詳情
              </PageLink>
              <PageLink href="/showcase">
                <RefreshCw className="h-4 w-4" />
                看作品亮點
              </PageLink>
            </div>
          </div>
          <div className="rounded-lg border border-[#ded7c9] bg-[#fffdf8] p-5">
            <h3 className="text-lg font-semibold tracking-normal">展示時要點</h3>
            <ul className="mt-4 space-y-3">
              {proofPoints.map((point) => (
                <li key={point} className="flex gap-3 text-sm leading-6 text-zinc-600">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-700" />
                  <span>{point}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>
    </main>
  );
}
