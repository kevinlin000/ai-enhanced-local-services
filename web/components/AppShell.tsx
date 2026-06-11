"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Bell,
  BookOpen,
  CalendarDays,
  ChevronRight,
  Compass,
  Heart,
  LogIn,
  LogOut,
  Menu,
  MessageSquareText,
  PenSquare,
  Presentation,
  Search,
  UserCircle,
  X,
} from "lucide-react";
import { useAuth } from "@/lib/auth";

const NAV_ITEMS = [
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
  {
    label: "食記",
    href: "/posts",
    icon: BookOpen,
    disabled: true,
  },
];

function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/" || pathname === "/shops";
  return pathname === href || pathname.startsWith(`${href}/`);
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
                : item.disabled
                  ? "cursor-not-allowed text-zinc-400"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
            } ${collapsed ? "justify-center px-3" : "gap-3 px-4"}`;

            if (item.disabled) {
              return (
                <div key={item.label} className={className} title="後續加入食記功能">
                  <Icon className="h-5 w-5" />
                  {!collapsed ? (
                    <>
                      <span className="flex-1">{item.label}</span>
                      <span className="rounded-full bg-background px-2 py-0.5 text-[10px] font-medium text-zinc-400">
                        soon
                      </span>
                    </>
                  ) : null}
                </div>
              );
            }

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
          {mounted ? (
            isAuthLoading ? null : isLoggedIn ? (
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
            )
          ) : null}

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
            <aside className="relative flex h-full w-[86vw] max-w-[340px] flex-col border-r bg-[rgb(255_253_248)] shadow-2xl">
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
                      : item.disabled
                        ? "cursor-not-allowed text-zinc-400"
                        : "text-muted-foreground hover:bg-muted hover:text-foreground"
                  }`;

                  if (item.disabled) {
                    return (
                      <div key={item.label} className={className}>
                        <Icon className="h-5 w-5" />
                        <span className="flex-1">{item.label}</span>
                        <span className="rounded-full bg-background px-2 py-0.5 text-[10px] font-medium text-zinc-400">
                          soon
                        </span>
                      </div>
                    );
                  }

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
                {mounted ? (
                  isAuthLoading ? null : isLoggedIn ? (
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
                  )
                ) : null}
                <p className="px-3 text-[11px] text-muted-foreground/70">Version: 1.4.0</p>
              </div>
            </aside>
          </div>
        ) : null}
        {children}
      </div>
    </div>
  );
}
