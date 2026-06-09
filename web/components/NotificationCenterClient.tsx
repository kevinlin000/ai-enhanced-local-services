"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { javaApi, type UserNotification } from "@/lib/api";

type Snapshot = {
  unreadCount: number;
  latestUnread: UserNotification | null;
};

function notificationKey(item: UserNotification | null) {
  return item ? `${item.id}:${item.status}` : "";
}

export function NotificationCenterClient() {
  const [snapshot, setSnapshot] = useState<Snapshot>({ unreadCount: 0, latestUnread: null });
  const [toast, setToast] = useState<UserNotification | null>(null);
  const seenLatestRef = useRef("");
  const initializedRef = useRef(false);

  const markReadAndDismiss = (item: UserNotification) => {
    setToast(null);
    setSnapshot((current) => ({
      ...current,
      unreadCount: Math.max(0, current.unreadCount - 1),
      latestUnread: current.latestUnread?.id === item.id ? null : current.latestUnread,
    }));
    void javaApi.markNotificationRead(item.id).catch(() => {
      // The next polling cycle will restore the unread count if the write failed.
    });
  };

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const response = await javaApi.notifications();
        if (!response.success || cancelled) return;
        const items = response.data.items ?? [];
        const latestUnread = items.find((item) => item.status === "UNREAD") ?? null;
        const key = notificationKey(latestUnread);
        setSnapshot({
          unreadCount: response.data.unreadCount ?? 0,
          latestUnread,
        });

        if (!initializedRef.current) {
          initializedRef.current = true;
          seenLatestRef.current = key;
          return;
        }
        if (latestUnread && key && key !== seenLatestRef.current) {
          seenLatestRef.current = key;
          setToast(latestUnread);
        }
      } catch {
        // Notification polling should never break the main product surface.
      }
    };

    void load();
    const timer = window.setInterval(load, 8000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 8000);
    return () => window.clearTimeout(timer);
  }, [toast]);

  return (
    <>
      {snapshot.unreadCount > 0 ? (
        <Link
          href="/notifications"
          className="fixed right-4 top-16 z-50 rounded-full border border-emerald-200 bg-white px-3 py-2 text-xs font-black text-emerald-800 shadow-lg shadow-black/10 md:right-5 md:top-20"
        >
          空位通知
          <span className="ml-2 rounded-full bg-emerald-700 px-2 py-0.5 text-white">
            {snapshot.unreadCount}
          </span>
        </Link>
      ) : null}

      {toast ? (
        <div className="fixed right-5 top-32 z-[70] w-[min(360px,calc(100vw-2rem))] overflow-hidden rounded-2xl border border-emerald-200 bg-white shadow-2xl shadow-black/20">
          <div className="bg-[#0f3324] px-4 py-3 text-white">
            <p className="text-xs font-semibold uppercase tracking-normal text-emerald-200">
              有空位了
            </p>
            <p className="mt-1 text-lg font-black">{toast.title}</p>
          </div>
          <div className="space-y-3 px-4 py-4">
            <p className="text-sm leading-6 text-zinc-600">{toast.body}</p>
            <div className="flex gap-2">
              <Link
                href={toast.shopId ? `/shops/${toast.shopId}` : "/notifications"}
                className="flex-1 rounded-full bg-emerald-700 px-4 py-2 text-center text-sm font-black text-white hover:bg-emerald-800"
                onClick={() => markReadAndDismiss(toast)}
              >
                查看釋出空位
              </Link>
              <button
                type="button"
                onClick={() => setToast(null)}
                className="rounded-full border border-zinc-200 px-4 py-2 text-sm font-bold text-zinc-600 hover:bg-zinc-50"
              >
                稍後
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
