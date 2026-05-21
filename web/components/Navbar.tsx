"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";

export function Navbar() {
  const { isLoggedIn, login, logout, mounted } = useAuth();

  return (
    <nav className="bg-background/80 sticky top-0 z-50 border-b backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-8">
        <Link href="/" className="font-bold tracking-tight">
          ByteBites<span className="text-primary">.</span>
        </Link>
        <div className="flex items-center gap-2">
          <Link href="/shops">
            <Button variant="ghost" size="sm">
              商家
            </Button>
          </Link>
          <Link href="/ai">
            <Button variant="ghost" size="sm">
              AI 搜尋
            </Button>
          </Link>
          {mounted
            ? isLoggedIn
              ? (
                  <Button variant="outline" size="sm" onClick={logout}>
                    登出
                  </Button>
                )
              : (
                  <Button
                    size="sm"
                    onClick={login}
                    className="bg-green-600 hover:bg-green-700"
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
