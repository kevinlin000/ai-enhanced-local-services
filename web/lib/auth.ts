"use client";

import { useEffect, useState } from "react";

const KEY = "bytebites_token";

export function useAuth() {
  const [token, setToken] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setToken(localStorage.getItem(KEY));
    setMounted(true);
  }, []);

  const login = () => {
    const javaApi = process.env.NEXT_PUBLIC_JAVA_API ?? "http://localhost:8081";
    window.location.href = `${javaApi}/api/auth/line/login`;
  };

  const logout = () => {
    localStorage.removeItem(KEY);
    setToken(null);
  };

  return { token, isLoggedIn: !!token, login, logout, mounted };
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(KEY);
}
