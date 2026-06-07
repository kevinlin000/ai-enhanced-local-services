"use client";

import { useEffect, useState } from "react";

const KEY = "bytebites_token";

export type AuthUser = {
  id: number;
  displayName: string;
  pictureUrl?: string | null;
  lineLinked: boolean;
};

export function useAuth() {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const storedToken = localStorage.getItem(KEY);
    setToken(storedToken);
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!token) {
      setUser(null);
      return;
    }

    let cancelled = false;
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
          return;
        }
        localStorage.removeItem(KEY);
        setToken(null);
        setUser(null);
      })
      .catch(() => {
        if (!cancelled) {
          localStorage.removeItem(KEY);
          setToken(null);
          setUser(null);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [token]);

  const login = () => {
    const javaApi = process.env.NEXT_PUBLIC_JAVA_API ?? "http://localhost:8081";
    window.location.href = `${javaApi}/api/auth/line/login`;
  };

  const logout = () => {
    localStorage.removeItem(KEY);
    setToken(null);
    setUser(null);
  };

  return { token, user, isLoggedIn: !!token, login, logout, mounted };
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(KEY);
}
