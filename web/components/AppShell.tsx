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
  Search,
  UserCircle,
} from "lucide-react";
import { useAuth } from "@/lib/auth";

const NAV_ITEMS = [
  {
    label: "與 AI 助手聊天",
    href: "/ai",
    icon: MessageSquareText,
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

  useEffect(() => {
    const stored = window.localStorage.getItem("bytebites_sidebar_collapsed");
    if (stored === "true") setCollapsed(true);
  }, []);

  const toggleCollapsed = () => {
    setCollapsed((current) => {
      const next = !current;
      window.localStorage.setItem("bytebites_sidebar_collapsed", String(next));
      return next;
    });
  };

  const shellClass = collapsed
    ? "min-h-screen bg-[#f6f1e8] text-[#171512] md:grid md:grid-cols-[84px_minmax(0,1fr)]"
    : "min-h-screen bg-[#f6f1e8] text-[#171512] md:grid md:grid-cols-[292px_minmax(0,1fr)]";

  const displayName = mounted && isAuthLoading
    ? "驗證中"
    : mounted && isLoggedIn
      ? user?.displayName ?? "ByteBites User"
      : "請先登入";
  const pictureUrl = mounted && isLoggedIn ? user?.pictureUrl : null;

  return (
    <div className={shellClass}>
      <aside className="hidden border-r border-black/10 bg-[#f7f3ec] md:sticky md:top-0 md:flex md:h-screen md:flex-col">
        <div className={`flex h-24 items-center ${collapsed ? "justify-center px-2" : "px-8"}`}>
          <Link href="/" className={`${collapsed ? "text-3xl" : "text-4xl"} font-black tracking-[-0.08em]`}>
            bb
          </Link>
        </div>

        <div className={`${collapsed ? "px-3" : "px-8"} pb-6`}>
          <div className={`flex items-center gap-4 ${collapsed ? "justify-center" : ""}`}>
            <div className="flex h-14 w-14 shrink-0 items-center justify-center overflow-hidden rounded-full bg-white shadow-sm ring-1 ring-black/5">
              {pictureUrl ? (
                <img
                  src={pictureUrl}
                  alt={displayName}
                  className="h-full w-full object-cover"
                  referrerPolicy="no-referrer"
                />
              ) : (
                <UserCircle className="h-8 w-8 text-zinc-500" />
              )}
            </div>
            {!collapsed ? (
              <div className="min-w-0">
                <p className="truncate text-lg font-black tracking-[-0.03em]">{displayName}</p>
                <p className="mt-0.5 text-xs font-medium text-zinc-500">
                  {mounted && isAuthLoading ? "正在確認 LINE 登入" : mounted && isLoggedIn ? "LINE 已登入" : "未登入"}
                </p>
              </div>
            ) : null}
          </div>
        </div>

        <div className={`${collapsed ? "px-3" : "px-6"} pb-5`}>
          <button
            type="button"
            onClick={() => {
              if (pathname !== "/ai") window.location.href = "/ai";
            }}
            className={`flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-left text-base font-bold hover:bg-black/5 ${
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
            const className = `flex items-center rounded-xl py-3 text-[15px] font-bold transition ${
              active
                ? "bg-[#e9ddbd] text-[#171512]"
                : item.disabled
                  ? "cursor-not-allowed text-zinc-400"
                  : "text-[#27231d] hover:bg-black/5"
            } ${collapsed ? "justify-center px-3" : "gap-4 px-5"}`;

            if (item.disabled) {
              return (
                <div key={item.label} className={className} title="後續加入食記功能">
                  <Icon className="h-5 w-5" />
                  {!collapsed ? (
                    <>
                      <span className="flex-1">{item.label}</span>
                      <span className="rounded-full bg-white px-2 py-0.5 text-[10px] font-black text-zinc-400">
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

        <div className={`space-y-3 ${collapsed ? "px-3" : "px-6"} py-6`}>
          {mounted ? (
            isAuthLoading ? null : isLoggedIn ? (
              <button
                type="button"
                onClick={logout}
                className={`flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-left text-sm font-bold hover:bg-black/5 ${
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
                className={`flex w-full items-center gap-3 rounded-2xl bg-emerald-700 px-4 py-3 text-left text-sm font-black text-white hover:bg-emerald-800 ${
                  collapsed ? "justify-center" : ""
                }`}
                title="用 LINE 登入"
              >
                <LogIn className="h-5 w-5" />
                {!collapsed ? "用 LINE 登入" : null}
              </button>
            )
          ) : null}

          {!collapsed ? <p className="px-3 text-[11px] text-zinc-400">Version: 1.4.0</p> : null}
        </div>
      </aside>

      <div className="flex min-w-0 flex-col">
        <header className="sticky top-0 z-40 hidden h-16 items-center justify-between border-b border-black/10 bg-[#f7f3ec]/92 px-7 backdrop-blur md:flex">
          <button
            type="button"
            onClick={toggleCollapsed}
            className="rounded-full p-2 text-zinc-600 hover:bg-black/5 hover:text-zinc-950"
            aria-label={collapsed ? "展開側欄" : "收合側欄"}
          >
            <Menu className="h-5 w-5" />
          </button>
          <Link href="/" className="text-4xl font-black tracking-[-0.06em]">
            ByteBites
          </Link>
          <Link
            href="/ai"
            className="flex w-[280px] items-center gap-2 rounded-full border border-black/10 bg-[#eee8dc] px-4 py-2.5 text-sm font-bold text-zinc-500 transition hover:bg-white"
          >
            <Search className="h-4 w-4" />
            找餐廳 問 ByteBites AI
          </Link>
        </header>

        <header className="sticky top-0 z-40 flex h-14 items-center justify-between border-b border-black/10 bg-[#f7f3ec]/90 px-4 backdrop-blur md:hidden">
          <Link href="/" className="text-2xl font-black tracking-[-0.08em]">
            bb
          </Link>
          <div className="flex items-center gap-2">
            <Link href="/ai" className="rounded-full bg-emerald-700 px-3 py-1.5 text-xs font-black text-white">
              AI Chat
            </Link>
            <Link href="/shops" className="rounded-full border border-black/10 px-3 py-1.5 text-xs font-black">
              探索
            </Link>
          </div>
        </header>
        {children}
      </div>
    </div>
  );
}
