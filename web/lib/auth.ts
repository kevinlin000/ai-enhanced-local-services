"use client";

import { useEffect, useState } from "react";

const KEY = "bytebites_token";

function browserSafeJavaApi(): string {
  const configured = process.env.NEXT_PUBLIC_JAVA_API ?? "/api/java";
  if (configured.startsWith("http://localhost") || configured.startsWith("http://127.0.0.1")) {
    return "/api/java";
  }
  return configured;
}

export type AuthUser = {
  id: number;
  displayName: string;
  pictureUrl?: string | null;
  lineLinked: boolean;
  lineUserId?: string | null;
};

export type AuthStatus = "loading" | "validating" | "authenticated" | "anonymous" | "expired";

export function useAuth() {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [mounted, setMounted] = useState(false);
  const [authStatus, setAuthStatus] = useState<AuthStatus>("loading");

  useEffect(() => {
    const storedToken = localStorage.getItem(KEY);
    setToken(storedToken);
    setAuthStatus("validating");
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted) {
      return;
    }

    let cancelled = false;
    const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
    setAuthStatus("validating");
    fetch("/api/java/api/auth/me", {
      headers,
      credentials: "same-origin",
      cache: "no-store",
    })
      .then((res) => {
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
        return res.json() as Promise<{ success: boolean; data?: AuthUser }>;
      })
      .then((payload) => {
        if (cancelled) return;
        if (payload.success && payload.data) {
          setUser(payload.data);
          setAuthStatus("authenticated");
          return;
        }
        if (token) localStorage.removeItem(KEY);
        setToken(null);
        setUser(null);
        setAuthStatus(token ? "expired" : "anonymous");
      })
      .catch(() => {
        if (!cancelled) {
          if (token) localStorage.removeItem(KEY);
          setToken(null);
          setUser(null);
          setAuthStatus(token ? "expired" : "anonymous");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [mounted, token]);

  const login = () => {
    const javaApi = browserSafeJavaApi();
    window.location.href = `${javaApi}/api/auth/line/login`;
  };

  const logout = () => {
    localStorage.removeItem(KEY);
    void fetch("/api/java/api/auth/logout", {
      method: "POST",
      credentials: "same-origin",
      cache: "no-store",
    });
    setToken(null);
    setUser(null);
    setAuthStatus("anonymous");
  };

  return {
    token,
    user,
    authStatus,
    isLoggedIn: authStatus === "authenticated" && !!user,
    isAuthLoading: authStatus === "loading" || authStatus === "validating",
    login,
    logout,
    mounted,
  };
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(KEY);
}
