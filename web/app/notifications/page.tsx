"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { javaApi, type AvailabilityWatch, type UserNotification } from "@/lib/api";
import { useAuth } from "@/lib/auth";

function formatSlot(item: { date?: string | null; time?: string | null; people?: number | null }) {
  return `${item.date ?? "-"} ${item.time ?? ""}${item.people ? ` · ${item.people} 人` : ""}`;
}

const watchTone: Record<AvailabilityWatch["status"], string> = {
  ACTIVE: "border-amber-200 bg-amber-50 text-amber-900",
  TRIGGERED: "border-emerald-200 bg-emerald-50 text-emerald-900",
  CANCELED: "border-zinc-200 bg-zinc-50 text-zinc-600",
  EXPIRED: "border-red-200 bg-red-50 text-red-700",
};

export default function NotificationsPage() {
  const { isLoggedIn, isAuthLoading, login, mounted } = useAuth();
  const [items, setItems] = useState<UserNotification[]>([]);
  const [watches, setWatches] = useState<AvailabilityWatch[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [busyWatchId, setBusyWatchId] = useState<number | null>(null);
  const [markingAll, setMarkingAll] = useState(false);

  const load = useCallback(async () => {
    if (mounted && isAuthLoading) {
      setLoading(true);
      return;
    }
    if (mounted && !isLoggedIn) {
      setItems([]);
      setWatches([]);
      setUnreadCount(0);
      setLoading(false);
      setError("");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const [notifications, watchResponse] = await Promise.all([
        javaApi.notifications(),
        javaApi.availabilityWatches(),
      ]);
      if (!notifications.success) throw new Error(notifications.errorMsg ?? "讀取通知失敗");
      if (!watchResponse.success) throw new Error(watchResponse.errorMsg ?? "讀取空位追蹤失敗");
      setItems(notifications.data.items ?? []);
      setUnreadCount(notifications.data.unreadCount ?? 0);
      setWatches(watchResponse.data ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "讀取通知失敗");
      setItems([]);
      setWatches([]);
    } finally {
      setLoading(false);
    }
  }, [isAuthLoading, isLoggedIn, mounted]);

  useEffect(() => {
    if (!mounted) return;
    void load();
  }, [load, mounted]);

  const markRead = async (id: number) => {
    setBusyId(id);
    setError("");
    try {
      const response = await javaApi.markNotificationRead(id);
      if (!response.success) throw new Error(response.errorMsg ?? "標記已讀失敗");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "標記已讀失敗");
    } finally {
      setBusyId(null);
    }
  };

  const markAllRead = async () => {
    if (unreadCount === 0) return;
    setMarkingAll(true);
    setError("");
    try {
      const response = await javaApi.markAllNotificationsRead();
      if (!response.success) throw new Error(response.errorMsg ?? "全部標記已讀失敗");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "全部標記已讀失敗");
    } finally {
      setMarkingAll(false);
    }
  };

  const cancelWatch = async (id: number) => {
    setBusyWatchId(id);
    setError("");
    try {
      const response = await javaApi.cancelAvailabilityWatch(id);
      if (!response.success) throw new Error(response.errorMsg ?? "取消追蹤失敗");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "取消追蹤失敗");
    } finally {
      setBusyWatchId(null);
    }
  };

  return (
    <main className="min-h-screen bg-background px-4 py-8 text-foreground md:px-8">
      <section className="mx-auto max-w-5xl">
        <div className="flex flex-col gap-5 border-b pb-6 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-xs font-medium uppercase tracking-normal text-muted-foreground">
              Availability Center
            </p>
            <h1 className="mt-3 text-3xl font-semibold tracking-normal md:text-4xl">空位釋出通知管理</h1>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-muted-foreground md:text-base">
              額滿時段釋出座位時會主動提醒。你可以在這裡查看通知、前往訂位，或取消不再需要的追蹤。
            </p>
          </div>
          <div className="w-fit rounded-lg border bg-muted/30 px-5 py-4">
            <p className="text-sm text-muted-foreground">未讀通知</p>
            <p className="mt-1 font-mono text-2xl font-medium">{unreadCount}</p>
          </div>
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
          <section className="rounded-lg border bg-background p-5 md:p-6">
            <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="text-xl font-medium">通知</h2>
                <p className="mt-1 text-sm text-zinc-500">有位時會優先提醒，請盡快完成訂位。</p>
              </div>
              <div className="flex flex-col gap-2 sm:flex-row">
                <Button variant="outline" onClick={markAllRead} disabled={loading || unreadCount === 0 || markingAll}>
                  {markingAll ? "處理中..." : "全部已讀"}
                </Button>
                <Button variant="outline" onClick={load} disabled={loading || isAuthLoading || (mounted && !isLoggedIn)}>
                  重新整理
                </Button>
              </div>
            </div>

            {mounted && !isAuthLoading && !isLoggedIn ? (
              <div className="mb-5 rounded-lg border border-amber-200 bg-amber-50 px-5 py-10 text-center">
                <p className="text-lg font-medium text-amber-950">請先用 LINE 登入</p>
                <p className="mt-2 text-sm leading-6 text-amber-800">
                  空位通知會綁定 LINE 帳號；登入後才能管理追蹤與接收通知。
                </p>
                <Button onClick={login} className="mt-5 rounded-full bg-emerald-700 hover:bg-emerald-800">
                  用 LINE 登入
                </Button>
              </div>
            ) : error ? (
              <div className="mb-5 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700">
                {error}
              </div>
            ) : null}

            {mounted && !isAuthLoading && !isLoggedIn ? null : loading ? (
              <div className="rounded-lg border border-zinc-200 bg-zinc-50 px-5 py-10 text-center text-zinc-500">
                讀取通知中...
              </div>
            ) : items.length === 0 ? (
              <div className="rounded-lg border border-zinc-200 bg-zinc-50 px-5 py-10 text-center">
                <p className="text-lg font-medium">目前沒有通知</p>
                <p className="mt-2 text-sm text-zinc-500">額滿時段釋出後會顯示在這裡。</p>
              </div>
            ) : (
              <div className="space-y-3">
                {items.map((item) => (
                  <article
                    key={item.id}
                    className={`rounded-lg border p-4 ${
                      item.status === "UNREAD"
                        ? "border-emerald-200 bg-emerald-50"
                        : "border-zinc-200 bg-[#fffdf8]"
                    }`}
                  >
                    <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                      <div>
                        <p className="text-lg font-medium">{item.title}</p>
                        <p className="mt-1 text-sm leading-6 text-zinc-600">{item.body}</p>
                        <p className="mt-2 text-xs font-medium text-zinc-400">{formatSlot(item)}</p>
                      </div>
                      <span className="w-fit rounded-full bg-white px-3 py-1 text-xs font-medium text-zinc-600">
                        {item.status === "UNREAD" ? "未讀" : "已讀"}
                      </span>
                    </div>
                    <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:flex-wrap">
                      {item.shopId ? (
                        <Link href={`/shops/${item.shopId}`}>
                          <Button size="sm" className="rounded-full bg-[#0b8a5b] hover:bg-[#087a50]">
                            前往訂位
                          </Button>
                        </Link>
                      ) : null}
                      {item.status === "UNREAD" ? (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => markRead(item.id)}
                          disabled={busyId === item.id}
                          className="rounded-full"
                        >
                          {busyId === item.id ? "處理中..." : "標記已讀"}
                        </Button>
                      ) : null}
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>

          <section className="rounded-lg border bg-background p-5 md:p-6">
            <h2 className="text-xl font-medium">追蹤中的空位</h2>
            <p className="mt-1 text-sm text-zinc-500">管理正在等待、已通知或已取消的時段。</p>
            <div className="mt-5 space-y-3">
              {watches.length === 0 ? (
                <div className="rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-8 text-center text-sm text-zinc-500">
                  尚未設定空位通知。
                </div>
              ) : (
                watches.map((watch) => (
                  <article key={watch.id} className="rounded-lg border border-zinc-200 bg-[#fffdf8] p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-medium">{watch.shopName}</p>
                        <p className="mt-1 text-sm text-zinc-500">{formatSlot(watch)}</p>
                      </div>
                      <span className={`rounded-full border px-3 py-1 text-xs font-medium ${watchTone[watch.status]}`}>
                        {watch.status}
                      </span>
                    </div>
                    <p className="mt-3 text-xs leading-5 text-zinc-500">
                      追蹤到 {watch.expiresAt}。有足夠座位釋出後會通知你前往訂位。
                    </p>
                    {watch.status === "ACTIVE" ? (
                      <div className="mt-3">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => cancelWatch(watch.id)}
                          disabled={busyWatchId === watch.id}
                          className="rounded-full"
                        >
                          {busyWatchId === watch.id ? "取消中..." : "取消追蹤"}
                        </Button>
                      </div>
                    ) : null}
                  </article>
                ))
              )}
            </div>
          </section>
        </div>
      </section>
    </main>
  );
}
