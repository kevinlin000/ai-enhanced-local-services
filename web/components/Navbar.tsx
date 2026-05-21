"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";

export function Navbar() {
  const { isLoggedIn, login, logout, mounted } = useAuth();

  return (
    <nav className="bg-background/80 sticky top-0 z-50 border-b backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4 md:px-8">
        <Link href="/" className="font-bold tracking-tight">
          ByteBites<span className="text-primary">.</span>
        </Link>
        <div className="flex items-center gap-1 md:gap-2">
          <Link href="/shops">
            <Button variant="ghost" size="sm" className="px-2 text-xs md:px-3 md:text-sm">
              商家
            </Button>
          </Link>
          <Link href="/ai">
            <Button variant="ghost" size="sm" className="px-2 text-xs md:px-3 md:text-sm">
              AI 搜尋
            </Button>
          </Link>
          {mounted
            ? isLoggedIn
              ? (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={logout}
                    className="px-2 text-xs md:px-3 md:text-sm"
                  >
                    登出
                  </Button>
                )
              : (
                  <Button
                    size="sm"
                    onClick={login}
                    className="bg-primary hover:bg-primary/90 px-2 text-xs md:px-3 md:text-sm"
                  >
                    用 LINE 登入
                  </Button>
                )
            : null}
        </div>
      </div>
    </nav>
  );
}
