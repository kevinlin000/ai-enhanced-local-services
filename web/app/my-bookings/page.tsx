"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { javaApi, type MyBooking } from "@/lib/api";

const statusCopy: Record<MyBooking["status"], { label: string; tone: string; helper: string }> = {
  PENDING_PAYMENT: {
    label: "待付訂金",
    tone: "border-amber-200 bg-amber-50 text-amber-900",
    helper: "位子已保留，完成訂金後才算付款完成。",
  },
  PAID: {
    label: "已付款",
    tone: "border-emerald-200 bg-emerald-50 text-emerald-900",
    helper: "訂金已完成，此訂位已成立。",
  },
  CONFIRMED: {
    label: "已確認",
    tone: "border-emerald-200 bg-emerald-50 text-emerald-900",
    helper: "此店家免訂金，訂位已成立。",
  },
  CANCELED: {
    label: "已取消",
    tone: "border-zinc-200 bg-zinc-50 text-zinc-600",
    helper: "訂位已取消，店家容量已釋放。",
  },
};

function formatDateTime(booking: MyBooking) {
  return `${booking.date} ${booking.time}`;
}

export default function MyBookingsPage() {
  const [bookings, setBookings] = useState<MyBooking[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyCode, setBusyCode] = useState<string | null>(null);

  const loadBookings = async () => {
    setLoading(true);
    setError("");
    try {
      const response = await javaApi.myBookings();
      if (!response.success) {
        setError(response.errorMsg ?? "讀取訂位失敗");
        setBookings([]);
      } else {
        setBookings(response.data ?? []);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "讀取訂位失敗");
      setBookings([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadBookings();
  }, []);

  const pay = async (bookingCode: string) => {
    setBusyCode(bookingCode);
    setError("");
    try {
      const response = await javaApi.payBookingWithTestCard(bookingCode);
      if (!response.success) {
        setError(response.errorMsg ?? "付款失敗");
      }
      await loadBookings();
    } catch (err) {
      setError(err instanceof Error ? err.message : "付款失敗");
    } finally {
      setBusyCode(null);
    }
  };

  const cancel = async (bookingCode: string) => {
    setBusyCode(bookingCode);
    setError("");
    try {
      const response = await javaApi.cancelBooking(bookingCode);
      if (!response.success) {
        setError(response.errorMsg ?? "取消訂位失敗");
      }
      await loadBookings();
    } catch (err) {
      setError(err instanceof Error ? err.message : "取消訂位失敗");
    } finally {
      setBusyCode(null);
    }
  };

  return (
    <main className="min-h-screen bg-[#f4f0e7] px-4 py-8 text-[#171512] md:px-8">
      <section className="mx-auto max-w-5xl">
        <div className="rounded-[2rem] bg-[#0f3324] p-8 text-white shadow-2xl shadow-emerald-950/20 md:p-10">
          <p className="mb-4 text-xs font-semibold uppercase tracking-[0.38em] text-emerald-200">
            ByteBites Reservations
          </p>
          <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
            <div>
              <h1 className="max-w-2xl text-4xl font-black leading-tight tracking-tight md:text-5xl">
                我的訂位
              </h1>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-emerald-50/80 md:text-base">
                管理已保留、待付款、已付款與已取消的訂位。Demo mode 使用 user_id=1001；正式上線會改由 LINE/JWT 決定 ownership。
              </p>
            </div>
            <Link href="/ai">
              <Button className="rounded-full bg-white px-6 text-[#0f3324] hover:bg-emerald-50">
                回 AI 訂位
              </Button>
            </Link>
          </div>
        </div>

        <div className="mt-6 rounded-[1.5rem] border border-black/10 bg-white p-5 shadow-xl shadow-black/5 md:p-6">
          <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="text-2xl font-black">訂位紀錄</h2>
              <p className="mt-1 text-sm text-zinc-500">付款與取消都會同步更新店家 slot inventory。</p>
            </div>
            <Button variant="outline" onClick={loadBookings} disabled={loading}>
              重新整理
            </Button>
          </div>

          {error ? (
            <div className="mb-5 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">
              {error}
            </div>
          ) : null}

          {loading ? (
            <div className="rounded-2xl border border-zinc-200 bg-zinc-50 px-5 py-10 text-center text-zinc-500">
              讀取訂位中...
            </div>
          ) : bookings.length === 0 ? (
            <div className="rounded-2xl border border-zinc-200 bg-zinc-50 px-5 py-10 text-center">
              <p className="text-lg font-bold">目前沒有訂位</p>
              <p className="mt-2 text-sm text-zinc-500">從 AI 搜尋或店家詳情建立訂位後，會出現在這裡。</p>
            </div>
          ) : (
            <div className="space-y-4">
              {bookings.map((booking) => {
                const status = statusCopy[booking.status];
                const canPay = booking.status === "PENDING_PAYMENT" && booking.needsDeposit;
                const canCancel = booking.status !== "CANCELED";
                const busy = busyCode === booking.bookingCode;

                return (
                  <article
                    key={booking.bookingCode}
                    className="overflow-hidden rounded-[1.25rem] border border-zinc-200 bg-[#fffdf8] shadow-sm"
                  >
                    <div className="flex flex-col gap-4 border-b border-zinc-200 bg-white px-5 py-4 md:flex-row md:items-center md:justify-between">
                      <div>
                        <p className="text-xl font-black">{booking.shopName}</p>
                        <p className="mt-1 font-mono text-sm text-zinc-500">{booking.bookingCode}</p>
                      </div>
                      <span className={`w-fit rounded-full border px-4 py-1.5 text-sm font-black ${status.tone}`}>
                        {status.label}
                      </span>
                    </div>

                    <div className="grid gap-4 px-5 py-5 md:grid-cols-4">
                      <div>
                        <p className="text-xs font-bold uppercase tracking-widest text-zinc-400">時間</p>
                        <p className="mt-1 text-lg font-bold">{formatDateTime(booking)}</p>
                      </div>
                      <div>
                        <p className="text-xs font-bold uppercase tracking-widest text-zinc-400">人數</p>
                        <p className="mt-1 text-lg font-bold">{booking.people} 人</p>
                      </div>
                      <div>
                        <p className="text-xs font-bold uppercase tracking-widest text-zinc-400">訂金</p>
                        <p className="mt-1 text-lg font-bold">
                          {booking.needsDeposit ? `NT$ ${booking.depositTotal}` : "免訂金"}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs font-bold uppercase tracking-widest text-zinc-400">交易編號</p>
                        <p className="mt-1 truncate font-mono text-sm font-bold">
                          {booking.paymentTransId ?? "-"}
                        </p>
                      </div>
                    </div>

                    <div className="flex flex-col gap-3 border-t border-zinc-200 bg-white px-5 py-4 md:flex-row md:items-center md:justify-between">
                      <p className="text-sm text-zinc-500">{status.helper}</p>
                      <div className="flex gap-2">
                        {canPay ? (
                          <Button
                            onClick={() => pay(booking.bookingCode)}
                            disabled={busy}
                            className="rounded-full bg-[#0b8a5b] px-5 hover:bg-[#087a50]"
                          >
                            {busy ? "處理中..." : "支付訂金"}
                          </Button>
                        ) : null}
                        {canCancel ? (
                          <Button
                            variant="outline"
                            onClick={() => cancel(booking.bookingCode)}
                            disabled={busy}
                            className="rounded-full px-5"
                          >
                            {busy ? "處理中..." : "取消訂位"}
                          </Button>
                        ) : null}
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </div>
      </section>
    </main>
  );
}
