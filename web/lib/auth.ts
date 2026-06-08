"use client";

import { useEffect, useState } from "react";

const KEY = "bytebites_token";

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
    setAuthStatus(storedToken ? "validating" : "anonymous");
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!token) {
      setUser(null);
      if (mounted) setAuthStatus((current) => current === "expired" ? current : "anonymous");
      return;
    }

    let cancelled = false;
    setAuthStatus("validating");
    fetch("/api/java/api/auth/me", {
      headers: { Authorization: `Bearer ${token}` },
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
        localStorage.removeItem(KEY);
        setToken(null);
        setUser(null);
        setAuthStatus("expired");
      })
      .catch(() => {
        if (!cancelled) {
          localStorage.removeItem(KEY);
          setToken(null);
          setUser(null);
          setAuthStatus("expired");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [mounted, token]);

  const login = () => {
    const javaApi = process.env.NEXT_PUBLIC_JAVA_API ?? "/api/java";
    window.location.href = `${javaApi}/api/auth/line/login`;
  };

  const logout = () => {
    localStorage.removeItem(KEY);
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
