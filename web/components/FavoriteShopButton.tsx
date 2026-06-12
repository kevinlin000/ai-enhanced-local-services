"use client";

import { useEffect, useState } from "react";
import { Heart } from "lucide-react";
import { javaApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type FavoriteShopButtonProps = {
  shopId: number;
  compact?: boolean;
  inverted?: boolean;
};

export function FavoriteShopButton({ shopId, compact = false, inverted = false }: FavoriteShopButtonProps) {
  const { isLoggedIn, isAuthLoading, login, mounted } = useAuth();
  const [favorited, setFavorited] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (mounted && isAuthLoading) return;
    if (mounted && !isLoggedIn) {
      setFavorited(false);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    javaApi.favoriteStatus(shopId)
      .then((response) => {
        if (!cancelled && response.success) setFavorited(Boolean(response.data.favorited));
      })
      .catch(() => {
        // Keep the restaurant page usable even if favorite status is unavailable.
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [isAuthLoading, isLoggedIn, mounted, shopId]);

  const toggle = async () => {
    if (busy) return;
    if (mounted && isAuthLoading) return;
    if (mounted && !isLoggedIn) {
      login();
      return;
    }
    setBusy(true);
    const next = !favorited;
    setFavorited(next);
    try {
      const response = next
        ? await javaApi.saveFavoriteShop(shopId)
        : await javaApi.removeFavoriteShop(shopId);
      if (response.success) setFavorited(Boolean(response.data.favorited));
      else setFavorited(!next);
    } catch {
      setFavorited(!next);
    } finally {
      setBusy(false);
    }
  };

  const base = compact
    ? "inline-flex h-10 w-10 items-center justify-center rounded-full border"
    : "inline-flex items-center justify-center gap-2 rounded-full border px-4 py-2 text-sm font-black";
  const loginRequired = mounted && !isAuthLoading && !isLoggedIn;
  const label = loginRequired ? "登入收藏" : favorited ? "已收藏" : "收藏餐廳";
  const ariaLabel = loginRequired ? "登入後收藏餐廳" : favorited ? "取消收藏餐廳" : "收藏餐廳";
  const tone = favorited
    ? "border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100"
    : inverted
      ? "border-white/35 bg-white/20 text-white backdrop-blur hover:bg-white/30"
      : "border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-50";

  return (
    <button
      type="button"
      onClick={toggle}
      disabled={loading || busy}
      aria-pressed={favorited}
      aria-label={ariaLabel}
      title={ariaLabel}
      className={`${base} ${tone} disabled:cursor-not-allowed disabled:opacity-60`}
    >
      <Heart className={`h-4 w-4 ${favorited ? "fill-current" : ""}`} />
      {compact ? null : <span>{label}</span>}
    </button>
  );
}
