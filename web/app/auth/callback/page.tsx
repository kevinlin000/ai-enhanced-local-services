"use client";

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";

function AuthCallbackContent() {
  const router = useRouter();
  const params = useSearchParams();

  useEffect(() => {
    const token = params.get("token");
    if (token) {
      localStorage.setItem("bytebites_token", token);
      router.replace("/");
    } else {
      const error = params.get("error") ?? "LINE login failed";
      router.replace(`/?login_failed=${encodeURIComponent(error)}`);
    }
  }, [params, router]);

  return <p className="text-muted-foreground">登入中...</p>;
}

export default function AuthCallback() {
  return (
    <main className="flex min-h-screen items-center justify-center">
      <Suspense fallback={<p className="text-muted-foreground">登入中...</p>}>
        <AuthCallbackContent />
      </Suspense>
    </main>
  );
}
