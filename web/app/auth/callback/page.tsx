"use client";

import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";

export default function AuthCallback() {
  const router = useRouter();
  const params = useSearchParams();

  useEffect(() => {
    const token = params.get("token");
    if (token) {
      localStorage.setItem("bytebites_token", token);
      router.replace("/");
    } else {
      router.replace("/?login_failed=1");
    }
  }, [params, router]);

  return (
    <main className="flex min-h-screen items-center justify-center">
      <p className="text-muted-foreground">登入中...</p>
    </main>
  );
}
