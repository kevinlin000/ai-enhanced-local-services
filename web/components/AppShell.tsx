"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Bell,
  BookOpen,
  CalendarDays,
  ChevronRight,
  Compass,
  Heart,
  LogIn,
  LogOut,
  MessageSquareText,
  PenSquare,
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
  const { isLoggedIn, login, logout, mounted } = useAuth();

  return (
    <div className="min-h-screen bg-[#f6f1e8] text-[#171512] md:grid md:grid-cols-[292px_minmax(0,1fr)]">
      <aside className="hidden border-r border-black/10 bg-[#f7f3ec] md:sticky md:top-0 md:flex md:h-screen md:flex-col">
        <div className="flex h-24 items-center px-8">
          <Link href="/" className="text-4xl font-black tracking-[-0.08em]">
            bb
          </Link>
        </div>

        <div className="px-6 pb-5">
          <button
            type="button"
            onClick={() => {
              if (pathname !== "/ai") window.location.href = "/ai";
            }}
            className="flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-left text-base font-bold hover:bg-black/5"
          >
            <PenSquare className="h-5 w-5" />
            開始新對話
          </button>
        </div>

        <nav className="flex-1 space-y-1 px-3">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const active = isActive(pathname, item.href);
            const className = `flex items-center gap-4 rounded-xl px-5 py-3 text-[15px] font-bold transition ${
              active
                ? "bg-[#e9ddbd] text-[#171512]"
                : item.disabled
                  ? "cursor-not-allowed text-zinc-400"
                  : "text-[#27231d] hover:bg-black/5"
            }`;

            if (item.disabled) {
              return (
                <div key={item.label} className={className} title="後續加入食記功能">
                  <Icon className="h-5 w-5" />
                  <span className="flex-1">{item.label}</span>
                  <span className="rounded-full bg-white px-2 py-0.5 text-[10px] font-black text-zinc-400">
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

        <div className="space-y-3 px-6 py-6">
          <div className="flex items-center gap-3 rounded-2xl px-3 py-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white">
              <UserCircle className="h-6 w-6 text-zinc-500" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-black">
                {mounted && isLoggedIn ? "ByteBites User" : "訪客模式"}
              </p>
              <p className="text-xs text-zinc-500">
                {mounted && isLoggedIn ? "LINE 已登入" : "Demo mode"}
              </p>
            </div>
          </div>

          {mounted ? (
            isLoggedIn ? (
              <button
                type="button"
                onClick={logout}
                className="flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-left text-sm font-bold hover:bg-black/5"
              >
                <LogOut className="h-5 w-5" />
                登出
              </button>
            ) : (
              <button
                type="button"
                onClick={login}
                className="flex w-full items-center gap-3 rounded-2xl bg-emerald-700 px-4 py-3 text-left text-sm font-black text-white hover:bg-emerald-800"
              >
                <LogIn className="h-5 w-5" />
                用 LINE 登入
              </button>
            )
          ) : null}

          <p className="px-3 text-[11px] text-zinc-400">Version: 1.4.0</p>
        </div>
      </aside>

      <div className="flex min-w-0 flex-col">
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
