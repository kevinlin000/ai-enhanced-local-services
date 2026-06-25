"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  AlertTriangle,
  Bell,
  CalendarDays,
  ChevronRight,
  Compass,
  Heart,
  LogIn,
  LogOut,
  Menu,
  MessageSquareText,
  MonitorPlay,
  PenSquare,
  Presentation,
  ReceiptText,
  Search,
  Store,
  UserCircle,
  X,
} from "lucide-react";
import { useAuth } from "@/lib/auth";

const NAV_ITEMS = [
  {
    label: "Demo 導覽",
    href: "/demo",
    icon: MonitorPlay,
  },
  {
    label: "與 AI 助手聊天",
    href: "/ai",
    icon: MessageSquareText,
  },
  {
    label: "專案亮點",
    href: "/showcase",
    icon: Presentation,
  },
  {
    label: "探索餐廳",
    href: "/",
    icon: Compass,
  },
  {
    label: "空位釋出通知管理",
    href: "/notifications",
    icon: Bell,
  },
  {
    label: "我的訂位",
    href: "/my-bookings",
    icon: CalendarDays,
  },
  {
    label: "收藏餐廳",
    href: "/favorites",
    icon: Heart,
  },
];

const MERCHANT_NAV_ITEMS = [
  {
    label: "營運總覽",
    href: "/merchant",
    icon: Store,
  },
  {
    label: "工作佇列",
    href: "/merchant#incident-queue",
    icon: AlertTriangle,
  },
  {
    label: "訂金退款",
    href: "/merchant#deposit-queue",
    icon: ReceiptText,
  },
  {
    label: "時段容量",
    href: "/merchant#slots",
    icon: CalendarDays,
  },
  {
    label: "店家清單",
    href: "/merchant#shops",
    icon: Store,
  },
];

function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/" || pathname === "/shops";
  return pathname === href || pathname.startsWith(`${href}/`);
}

function ProductFooter() {
  const links = [
    ["探索餐廳", "/shops"],
    ["AI 助手", "/ai"],
    ["我的訂位", "/my-bookings"],
    ["專案亮點", "/showcase"],
  ] as const;

  return (
    <footer className="border-t border-[rgb(222_216_203_/_0.82)] bg-[rgb(255_253_248_/_0.76)] px-5 py-8 md:px-8">
      <div className="mx-auto grid max-w-7xl gap-6 text-sm text-muted-foreground md:grid-cols-[1fr_auto] md:items-end">
        <div>
          <Link href="/" className="text-xl font-semibold tracking-normal text-[var(--bb-ink)]">
            ByteBites
          </Link>
          <p className="mt-2 max-w-2xl leading-6">
            台北餐廳搜尋、AI 推薦、訂位與通知管理。資料、交易狀態與商家操作分層處理。
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <span className="rounded-lg border border-[rgb(222_216_203_/_0.82)] bg-white px-3 py-1.5 text-xs font-medium text-[#5d5140]">
              599 家台北 active shops
            </span>
            <span className="rounded-lg border border-[rgb(222_216_203_/_0.82)] bg-white px-3 py-1.5 text-xs font-medium text-[#5d5140]">
              LINE login
            </span>
            <span className="rounded-lg border border-[rgb(222_216_203_/_0.82)] bg-white px-3 py-1.5 text-xs font-medium text-[#5d5140]">
              Java transaction state
            </span>
          </div>
        </div>
        <nav className="flex flex-wrap gap-x-5 gap-y-2 md:justify-end" aria-label="頁尾導覽">
          {links.map(([label, href]) => (
            <Link key={href} href={href} className="font-medium text-[#5d5140] hover:text-[var(--bb-ink)]">
              {label}
            </Link>
          ))}
        </nav>
      </div>
    </footer>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { isLoggedIn, isAuthLoading, login, logout, mounted, user } = useAuth();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    const stored = window.localStorage.getItem("bytebites_sidebar_collapsed");
    if (stored === "true") setCollapsed(true);
  }, []);

  useEffect(() => {
    setMobileMenuOpen(false);
  }, [pathname]);

  const toggleCollapsed = () => {
    setCollapsed((current) => {
      const next = !current;
      window.localStorage.setItem("bytebites_sidebar_collapsed", String(next));
      return next;
    });
  };

  const shellClass = collapsed
    ? "bb-premium-page min-h-screen text-foreground md:grid md:grid-cols-[76px_minmax(0,1fr)]"
    : "bb-premium-page min-h-screen text-foreground md:grid md:grid-cols-[272px_minmax(0,1fr)]";

  const displayName = mounted && isAuthLoading
    ? "驗證中"
    : mounted && isLoggedIn
      ? user?.displayName ?? "ByteBites User"
      : "請先登入";
  const pictureUrl = mounted && isLoggedIn ? user?.pictureUrl : null;

  if (pathname.startsWith("/merchant")) {
    return (
      <div className="min-h-screen bg-[#f7f6f2] text-foreground md:grid md:grid-cols-[248px_minmax(0,1fr)]">
        <aside className="hidden border-r border-stone-200 bg-[#fbfaf6] md:sticky md:top-0 md:flex md:h-screen md:flex-col">
          <div className="border-b border-stone-200 px-5 py-5">
            <Link href="/merchant" className="block text-2xl font-semibold tracking-normal text-[var(--bb-ink)]">
              ByteBites Ops
            </Link>
            <p className="mt-1 text-xs font-medium text-zinc-500">商家工作台</p>
          </div>

          <div className="border-b border-stone-200 px-5 py-5">
            <div className="flex items-center gap-3">
              <div
                className="bb-shell-avatar flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-background ring-1 ring-border"
                style={{ width: 48, height: 48, maxWidth: 48, maxHeight: 48 }}
              >
                {pictureUrl ? (
                  <img
                    src={pictureUrl}
                    alt={displayName}
                    width={48}
                    height={48}
                    className="bb-shell-avatar-image"
                    style={{ width: "100%", height: "100%", maxWidth: "100%", maxHeight: "100%", objectFit: "cover" }}
                    referrerPolicy="no-referrer"
                  />
                ) : (
                  <UserCircle className="h-8 w-8 text-zinc-500" />
                )}
              </div>
              <div className="min-w-0">
                <p className="truncate text-base font-medium tracking-normal">{displayName}</p>
                <p className="mt-0.5 text-xs font-medium text-zinc-500">
                  {mounted && isAuthLoading ? "正在確認 LINE 登入" : mounted && isLoggedIn ? "LINE 已登入" : "未登入"}
                </p>
              </div>
            </div>
          </div>

          <nav className="flex-1 space-y-1 px-3 py-4">
            {MERCHANT_NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              const active = item.href === "/merchant" ? pathname === "/merchant" : isActive(pathname, item.href);
              const className = `flex items-center gap-3 rounded-lg px-4 py-3 text-[15px] font-medium transition ${
                active ? "bb-shell-active" : "text-muted-foreground hover:bg-muted hover:text-foreground"
              }`;

              return (
                <Link key={item.label} href={item.href} className={className}>
                  <Icon className="h-5 w-5" />
                  <span className="flex-1">{item.label}</span>
                  <ChevronRight className="h-4 w-4 opacity-60" />
                </Link>
              );
            })}
          </nav>

          <div className="space-y-2 border-t border-stone-200 px-4 py-5">
            <Link
              href="/demo"
              className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              <MonitorPlay className="h-5 w-5" />
              Demo 導覽
            </Link>
            <Link
              href="/"
              className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              <Compass className="h-5 w-5" />
              切換消費者端
            </Link>
            {mounted && isLoggedIn ? (
              <button
                type="button"
                onClick={logout}
                className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm font-medium hover:bg-muted"
              >
                <LogOut className="h-5 w-5" />
                登出
              </button>
            ) : (
              <button
                type="button"
                onClick={login}
                className="flex w-full items-center gap-3 rounded-lg bg-emerald-700 px-3 py-2.5 text-left text-sm font-medium text-white hover:bg-emerald-800"
              >
                <LogIn className="h-5 w-5" />
                用 LINE 登入
              </button>
            )}
            <p className="px-3 text-[11px] text-muted-foreground/70">Version: 1.4.0</p>
          </div>
        </aside>

        <div className="flex min-w-0 flex-col">
          <header className="sticky top-0 z-40 flex h-16 items-center justify-between border-b border-stone-200 bg-[#fbfaf6]/90 px-4 backdrop-blur md:px-6">
            <div className="flex min-w-0 items-center gap-3">
              <Link href="/merchant" className="text-lg font-semibold tracking-normal md:hidden">
                Ops
              </Link>
              <div className="hidden min-w-0 md:block">
                <p className="text-sm font-semibold text-stone-900">商家營運台</p>
                <p className="text-xs font-medium text-zinc-500">時段容量、救場事件、訂金退款</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Link
                href="/demo"
                className="rounded-lg border border-stone-200 bg-white px-3 py-2 text-sm font-medium text-stone-700 hover:bg-stone-50"
              >
                Demo 導覽
              </Link>
            </div>
          </header>
          {children}
        </div>
      </div>
    );
  }

  return (
    <div className={shellClass}>
      <aside className="bb-shell-sidebar hidden border-r md:sticky md:top-0 md:flex md:h-screen md:flex-col">
        <div className={`flex h-20 items-center ${collapsed ? "justify-center px-2" : "px-6"}`}>
          <Link href="/" className={`${collapsed ? "text-2xl" : "text-3xl"} font-semibold tracking-normal text-[var(--bb-ink)]`}>
            bb
          </Link>
        </div>

        <div className={`${collapsed ? "px-3" : "px-6"} pb-5`}>
          <div className={`flex items-center gap-3 ${collapsed ? "justify-center" : ""}`}>
            <div
              className="bb-shell-avatar flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-background ring-1 ring-border"
              style={{ width: 48, height: 48, maxWidth: 48, maxHeight: 48 }}
            >
              {pictureUrl ? (
                <img
                  src={pictureUrl}
                  alt={displayName}
                  width={48}
                  height={48}
                  className="bb-shell-avatar-image"
                  style={{ width: "100%", height: "100%", maxWidth: "100%", maxHeight: "100%", objectFit: "cover" }}
                  referrerPolicy="no-referrer"
                />
              ) : (
                <UserCircle className="h-8 w-8 text-zinc-500" />
              )}
            </div>
            {!collapsed ? (
              <div className="min-w-0">
                <p className="truncate text-base font-medium tracking-normal">{displayName}</p>
                <p className="mt-0.5 text-xs font-medium text-zinc-500">
                  {mounted && isAuthLoading ? "正在確認 LINE 登入" : mounted && isLoggedIn ? "LINE 已登入" : "未登入"}
                </p>
              </div>
            ) : null}
          </div>
        </div>

        <div className={`${collapsed ? "px-3" : "px-4"} pb-5`}>
          <button
            type="button"
            onClick={() => {
              if (pathname !== "/ai") window.location.href = "/ai";
            }}
            className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm font-medium hover:bg-muted ${
              collapsed ? "justify-center" : ""
            }`}
            title="開始新對話"
          >
            <PenSquare className="h-5 w-5" />
            {!collapsed ? "開始新對話" : null}
          </button>
        </div>

        <nav className="flex-1 space-y-1 px-3">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const active = isActive(pathname, item.href);
            const className = `flex items-center rounded-lg py-2.5 text-[15px] font-medium transition ${
              active
                ? "bb-shell-active"
                : "text-muted-foreground hover:bg-muted hover:text-foreground"
            } ${collapsed ? "justify-center px-3" : "gap-3 px-4"}`;

            return (
              <Link key={item.label} href={item.href} className={className} title={item.label}>
                <Icon className="h-5 w-5" />
                {!collapsed ? (
                  <>
                    <span className="flex-1">{item.label}</span>
                    <ChevronRight className="h-4 w-4 opacity-60" />
                  </>
                ) : null}
              </Link>
            );
          })}
        </nav>

        <div className={`space-y-3 ${collapsed ? "px-3" : "px-4"} py-5`}>
          {mounted && isLoggedIn ? (
            <button
              type="button"
              onClick={logout}
              className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm font-medium hover:bg-muted ${
                collapsed ? "justify-center" : ""
              }`}
              title="登出"
            >
              <LogOut className="h-5 w-5" />
              {!collapsed ? "登出" : null}
            </button>
          ) : (
            <button
              type="button"
              onClick={login}
              className={`flex w-full items-center gap-3 rounded-lg bg-emerald-700 px-3 py-2.5 text-left text-sm font-medium text-white hover:bg-emerald-800 ${
                collapsed ? "justify-center" : ""
              }`}
              title="用 LINE 登入"
            >
              <LogIn className="h-5 w-5" />
              {!collapsed ? "用 LINE 登入" : null}
            </button>
          )}

          {!collapsed ? <p className="px-3 text-[11px] text-muted-foreground/70">Version: 1.4.0</p> : null}
        </div>
      </aside>

      <div className="flex min-w-0 flex-col">
        <header className="sticky top-0 z-40 hidden h-16 items-center justify-between border-b bg-[rgb(255_253_248_/_0.88)] px-6 backdrop-blur md:flex">
          <button
            type="button"
            onClick={toggleCollapsed}
            className="rounded-lg p-2 text-muted-foreground hover:bg-muted hover:text-foreground"
            aria-label={collapsed ? "展開側欄" : "收合側欄"}
          >
            <Menu className="h-5 w-5" />
          </button>
          <Link href="/" className="text-3xl font-semibold tracking-normal text-[var(--bb-ink)]">
            ByteBites
          </Link>
          <Link
            href="/ai"
            className="flex w-[260px] items-center gap-2 rounded-lg border border-[rgb(167_137_67_/_0.18)] bg-[rgb(255_253_248_/_0.72)] px-3 py-2 text-sm font-medium text-muted-foreground transition hover:border-[rgb(167_137_67_/_0.38)] hover:bg-[rgb(255_255_255_/_0.9)] hover:text-foreground"
          >
            <Search className="h-4 w-4" />
            找餐廳 問 ByteBites AI
          </Link>
        </header>

        <header className="sticky top-0 z-40 flex h-14 items-center justify-between border-b bg-[rgb(255_253_248_/_0.9)] px-4 backdrop-blur md:hidden">
          <button
            type="button"
            onClick={() => setMobileMenuOpen(true)}
            className="rounded-lg p-2 text-[var(--bb-ink)] hover:bg-muted"
            aria-label="開啟選單"
          >
            <Menu className="h-5 w-5" />
          </button>
          <Link href="/" className="text-2xl font-semibold tracking-normal">
            bb
          </Link>
          <div className="flex items-center gap-2">
            <Link href="/ai" className="rounded-lg bg-emerald-700 px-3 py-1.5 text-xs font-medium text-white">
              AI Chat
            </Link>
            <Link href="/shops" className="rounded-lg border px-3 py-1.5 text-xs font-medium">
              探索
            </Link>
          </div>
        </header>
        {mobileMenuOpen ? (
          <div className="fixed inset-0 z-50 md:hidden" role="dialog" aria-modal="true">
            <button
              type="button"
              className="absolute inset-0 bg-black/28"
              aria-label="關閉選單"
              onClick={() => setMobileMenuOpen(false)}
            />
            <aside className="relative flex h-full w-[86vw] max-w-[340px] flex-col border-r bg-[rgb(255_253_248)]">
              <div className="flex h-16 items-center justify-between border-b px-5">
                <Link href="/" className="text-3xl font-semibold tracking-normal text-[var(--bb-ink)]">
                  bb
                </Link>
                <button
                  type="button"
                  onClick={() => setMobileMenuOpen(false)}
                  className="rounded-lg p-2 text-muted-foreground hover:bg-muted hover:text-foreground"
                  aria-label="關閉選單"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              <div className="border-b px-5 py-5">
                <div className="flex items-center gap-3">
                  <div
                    className="flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-background ring-1 ring-border"
                    style={{ width: 46, height: 46 }}
                  >
                    {pictureUrl ? (
                      <img
                        src={pictureUrl}
                        alt={displayName}
                        width={46}
                        height={46}
                        className="h-full w-full object-cover"
                        referrerPolicy="no-referrer"
                      />
                    ) : (
                      <UserCircle className="h-8 w-8 text-zinc-500" />
                    )}
                  </div>
                  <div className="min-w-0">
                    <p className="truncate text-base font-medium tracking-normal">{displayName}</p>
                    <p className="mt-0.5 text-xs font-medium text-zinc-500">
                      {mounted && isAuthLoading ? "正在確認 LINE 登入" : mounted && isLoggedIn ? "LINE 已登入" : "未登入"}
                    </p>
                  </div>
                </div>
              </div>

              <div className="px-4 py-4">
                <button
                  type="button"
                  onClick={() => {
                    setMobileMenuOpen(false);
                    window.location.href = "/ai";
                  }}
                  className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm font-medium hover:bg-muted"
                >
                  <PenSquare className="h-5 w-5" />
                  開始新對話
                </button>
              </div>

              <nav className="flex-1 space-y-1 px-3">
                {NAV_ITEMS.map((item) => {
                  const Icon = item.icon;
                  const active = isActive(pathname, item.href);
                  const className = `flex items-center gap-3 rounded-lg px-4 py-3 text-[15px] font-medium transition ${
                    active
                      ? "bb-shell-active"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground"
                  }`;

                  return (
                    <Link key={item.label} href={item.href} className={className}>
                      <Icon className="h-5 w-5" />
                      <span className="flex-1">{item.label}</span>
                      <ChevronRight className="h-4 w-4 opacity-60" />
                    </Link>
                  );
                })}
              </nav>

              <div className="space-y-3 border-t px-4 py-5">
                {mounted && isLoggedIn ? (
                  <button
                    type="button"
                    onClick={() => {
                      logout();
                      setMobileMenuOpen(false);
                    }}
                    className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm font-medium hover:bg-muted"
                  >
                    <LogOut className="h-5 w-5" />
                    登出
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => {
                      setMobileMenuOpen(false);
                      login();
                    }}
                    className="flex w-full items-center gap-3 rounded-lg bg-emerald-700 px-3 py-2.5 text-left text-sm font-medium text-white hover:bg-emerald-800"
                  >
                    <LogIn className="h-5 w-5" />
                    用 LINE 登入
                  </button>
                )}
                <p className="px-3 text-[11px] text-muted-foreground/70">Version: 1.4.0</p>
              </div>
            </aside>
          </div>
        ) : null}
        {children}
        <ProductFooter />
      </div>
    </div>
  );
}
