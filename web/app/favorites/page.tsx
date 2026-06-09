"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Heart, MapPin, Star } from "lucide-react";
import { javaApi, type FavoriteShop } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { getStyleByTypeId } from "@/lib/categoryStyle";
import { proxyImageUrl } from "@/lib/photoProxy";
import { getBestShopCardPhoto, getShopOverview } from "@/lib/shopPhotoManifest";

function getPhoto(shop: FavoriteShop) {
  const fallback = shop.images?.startsWith("http") ? shop.images : null;
  return proxyImageUrl(getBestShopCardPhoto(shop.shopId, fallback));
}

function formatSpend(shop: FavoriteShop) {
  const overview = getShopOverview(shop.shopId);
  if (overview?.price_overview) return overview.price_overview;
  if (shop.avgPrice) return `NT$ ${shop.avgPrice}`;
  return "未提及";
}

export default function FavoritesPage() {
  const { isLoggedIn, isAuthLoading, login, mounted } = useAuth();
  const [items, setItems] = useState<FavoriteShop[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const grouped = useMemo(() => {
    return items.reduce<Record<string, FavoriteShop[]>>((acc, shop) => {
      const key = shop.district ?? shop.area ?? "其他區域";
      acc[key] = acc[key] ?? [];
      acc[key].push(shop);
      return acc;
    }, {});
  }, [items]);

  useEffect(() => {
    if (!mounted) return;
    if (isAuthLoading) return;
    if (!isLoggedIn) {
      setItems([]);
      setError("");
      setLoading(false);
      return;
    }
    javaApi.favoriteShops()
      .then((response) => {
        if (response.success) {
          setItems(response.data ?? []);
          setError("");
        } else {
          setError(response.errorMsg ?? "讀取收藏失敗");
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : "讀取收藏失敗"))
      .finally(() => setLoading(false));
  }, [isAuthLoading, isLoggedIn, mounted]);

  const remove = async (shopId: number) => {
    setItems((current) => current.filter((shop) => shop.shopId !== shopId));
    try {
      await javaApi.removeFavoriteShop(shopId);
    } catch {
      void javaApi.favoriteShops().then((response) => {
        if (response.success) setItems(response.data ?? []);
      });
    }
  };

  return (
    <main className="min-h-screen bg-[#f6f1e8] px-4 py-8 md:px-8">
      <section className="mx-auto max-w-6xl overflow-hidden rounded-[2rem] border border-black/10 bg-white shadow-2xl shadow-black/10">
        <div className="border-b bg-[#123326] px-6 py-8 text-white md:px-10 md:py-10">
          <p className="text-xs font-black uppercase tracking-normal text-emerald-200">
            Saved restaurants
          </p>
          <div className="mt-4 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
            <div>
              <h1 className="text-4xl font-black tracking-normal md:text-6xl">收藏餐廳</h1>
              <p className="mt-3 max-w-2xl text-sm leading-7 text-white/70">
                把想吃、想訂、想等空位的餐廳集中管理。之後回訪時可以快速查看詳情、訂位或建立空位提醒。
              </p>
            </div>
            <Link
              href="/shops"
              className="inline-flex rounded-full border border-white/25 px-5 py-3 text-sm font-black text-white hover:bg-white/10"
            >
              繼續探索
            </Link>
          </div>
        </div>

        <div className="p-5 md:p-8">
          {mounted && !isAuthLoading && !isLoggedIn ? (
            <div className="rounded-3xl border border-amber-200 bg-amber-50 p-10 text-center">
              <Heart className="mx-auto h-10 w-10 text-amber-700" />
              <h2 className="mt-4 text-2xl font-black text-amber-950">請先用 LINE 登入</h2>
              <p className="mt-2 text-sm leading-6 text-amber-800">
                收藏餐廳會綁定 LINE 帳號；登入後才能同步收藏、訂位與通知。
              </p>
              <button
                type="button"
                onClick={login}
                className="mt-6 inline-flex rounded-full bg-emerald-700 px-5 py-3 text-sm font-black text-white hover:bg-emerald-800"
              >
                用 LINE 登入
              </button>
            </div>
          ) : loading ? (
            <div className="rounded-2xl border border-dashed p-10 text-center text-zinc-500">
              讀取收藏中...
            </div>
          ) : error ? (
            <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-red-700">
              {error}
            </div>
          ) : items.length === 0 ? (
            <div className="rounded-3xl border border-dashed bg-[#fbfaf7] p-10 text-center">
              <Heart className="mx-auto h-10 w-10 text-zinc-300" />
              <h2 className="mt-4 text-2xl font-black">還沒有收藏餐廳</h2>
              <p className="mt-2 text-sm text-zinc-500">
                到店家詳情頁點「收藏餐廳」，之後就能在這裡快速回訪與訂位。
              </p>
              <Link
                href="/shops"
                className="mt-6 inline-flex rounded-full bg-emerald-700 px-5 py-3 text-sm font-black text-white hover:bg-emerald-800"
              >
                去探索餐廳
              </Link>
            </div>
          ) : (
            <div className="space-y-8">
              {Object.entries(grouped).map(([district, shops]) => (
                <section key={district}>
                  <div className="mb-3 flex items-center justify-between">
                    <h2 className="text-lg font-black">{district}</h2>
                    <span className="rounded-full bg-zinc-100 px-3 py-1 text-xs font-bold text-zinc-500">
                      {shops.length} 間
                    </span>
                  </div>
                  <div className="grid gap-4 md:grid-cols-2">
                    {shops.map((shop) => {
                      const style = getStyleByTypeId(shop.typeId);
                      const photo = getPhoto(shop);
                      return (
                        <article
                          key={shop.shopId}
                          className="overflow-hidden rounded-3xl border bg-white shadow-sm transition hover:-translate-y-0.5 hover:shadow-lg"
                        >
                          <div className="grid md:grid-cols-[180px_1fr]">
                            <Link href={`/shops/${shop.shopId}`} className="block h-44 bg-zinc-100 md:h-full">
                              {photo ? (
                                <img
                                  src={photo}
                                  alt={shop.name}
                                  className="h-full w-full object-cover"
                                />
                              ) : (
                                <div className={`flex h-full items-center justify-center bg-gradient-to-br ${style.gradient}`}>
                                  <span className="text-sm font-black text-zinc-500">{style.label}</span>
                                </div>
                              )}
                            </Link>
                            <div className="flex flex-col gap-4 p-5">
                              <div>
                                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                                  <Link href={`/shops/${shop.shopId}`} className="text-xl font-black hover:text-emerald-700">
                                    {shop.name}
                                  </Link>
                                  <button
                                    type="button"
                                    onClick={() => remove(shop.shopId)}
                                    className="rounded-full border border-rose-100 bg-rose-50 px-3 py-1 text-xs font-black text-rose-700 hover:bg-rose-100"
                                  >
                                    取消收藏
                                  </button>
                                </div>
                                <div className="mt-2 flex flex-wrap gap-2 text-xs text-zinc-500">
                                  <span className="rounded-full bg-zinc-100 px-2 py-1">{style.label}</span>
                                  {shop.mrtStation ? (
                                    <span className="rounded-full bg-zinc-100 px-2 py-1">
                                      <MapPin className="mr-1 inline h-3 w-3" />
                                      {shop.mrtStation}
                                    </span>
                                  ) : null}
                                </div>
                              </div>
                              <div className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-3">
                                <div>
                                  <p className="text-xs text-zinc-400">評分</p>
                                  <p className="font-black">
                                    <Star className="mr-1 inline h-3.5 w-3.5 text-amber-500" />
                                    {shop.score ? (shop.score / 10).toFixed(1) : "-"}
                                  </p>
                                </div>
                                <div>
                                  <p className="text-xs text-zinc-400">消費</p>
                                  <p className="font-black">{formatSpend(shop)}</p>
                                </div>
                                <div>
                                  <p className="text-xs text-zinc-400">評論</p>
                                  <p className="font-black">{shop.comments?.toLocaleString() ?? "-"}</p>
                                </div>
                              </div>
                              <div className="mt-auto flex gap-2">
                                <Link
                                  href={`/shops/${shop.shopId}`}
                                  className="flex-1 rounded-full bg-emerald-700 px-4 py-2 text-center text-sm font-black text-white hover:bg-emerald-800"
                                >
                                  查看 / 訂位
                                </Link>
                              </div>
                            </div>
                          </div>
                        </article>
                      );
                    })}
                  </div>
                </section>
              ))}
            </div>
          )}
        </div>
      </section>
    </main>
  );
}
