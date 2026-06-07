"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { javaApi, type MyBooking } from "@/lib/api";
import { useAuth } from "@/lib/auth";

declare global {
  interface Window {
    TPDirect: any;
  }
}

type PaymentMethod = "credit_card" | "line_pay" | "apple_pay" | "jkopay";

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
  EXPIRED: {
    label: "已逾期",
    tone: "border-red-200 bg-red-50 text-red-700",
    helper: "付款保留時間已過，店家容量已釋放。",
  },
};

const paymentMethods: { id: PaymentMethod; label: string; helper: string; badge: string }[] = [
  {
    id: "credit_card",
    label: "信用卡",
    helper: "TapPay sandbox 測試卡",
    badge: "測試卡",
  },
  {
    id: "line_pay",
    label: "LINE Pay",
    helper: "Demo wallet authorization",
    badge: "demo",
  },
  {
    id: "apple_pay",
    label: "Apple Pay",
    helper: "Demo wallet authorization",
    badge: "demo",
  },
  {
    id: "jkopay",
    label: "街口支付",
    helper: "Demo wallet authorization",
    badge: "demo",
  },
];

function formatDateTime(booking: MyBooking) {
  return `${booking.date} ${booking.time}`;
}

function formatHoldCountdown(holdExpiresAt: string | null | undefined, nowMs: number) {
  if (!holdExpiresAt) return null;
  const remainingMs = new Date(holdExpiresAt).getTime() - nowMs;
  if (remainingMs <= 0) return "已逾期";
  const totalSeconds = Math.ceil(remainingMs / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

export default function MyBookingsPage() {
  const { isLoggedIn, login, mounted, user } = useAuth();
  const lineUserId = user?.lineUserId ?? null;
  const [bookings, setBookings] = useState<MyBooking[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyCode, setBusyCode] = useState<string | null>(null);
  const [paymentBooking, setPaymentBooking] = useState<MyBooking | null>(null);
  const [cancelBooking, setCancelBooking] = useState<MyBooking | null>(null);
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("credit_card");
  const [paymentError, setPaymentError] = useState("");
  const [allowDemoFallback, setAllowDemoFallback] = useState(false);
  const [sdkReady, setSdkReady] = useState(false);
  const [nowMs, setNowMs] = useState(() => Date.now());

  const loadBookings = useCallback(async () => {
    if (mounted && !isLoggedIn) {
      setBookings([]);
      setLoading(false);
      setError("");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const response = await javaApi.myBookings(lineUserId);
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
  }, [isLoggedIn, lineUserId, mounted]);

  useEffect(() => {
    if (!mounted) return;
    void loadBookings();
  }, [loadBookings, mounted]);

  useEffect(() => {
    const timer = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    const tryInit = () => {
      if (typeof window === "undefined" || !window.TPDirect) return false;
      try {
        window.TPDirect.setupSDK(
          parseInt(process.env.NEXT_PUBLIC_TAPPAY_APP_ID ?? "0", 10),
          process.env.NEXT_PUBLIC_TAPPAY_APP_KEY ?? "",
          process.env.NEXT_PUBLIC_TAPPAY_ENV || "sandbox",
        );
      } catch {
        // TapPay SDK may already be initialized by another booking widget.
      }
      setSdkReady(true);
      return true;
    };

    if (tryInit()) return;
    const timer = window.setInterval(() => {
      if (tryInit()) window.clearInterval(timer);
    }, 200);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!paymentBooking || paymentMethod !== "credit_card" || !sdkReady) return;
    const tryMount = () => {
      if (!document.getElementById("my-bookings-tappay-number")) return false;
      try {
        window.TPDirect?.card.setup({
          fields: {
            number: { element: "#my-bookings-tappay-number", placeholder: "4242 4242 4242 4242" },
            expirationDate: { element: "#my-bookings-tappay-expiry", placeholder: "MM / YY" },
            ccv: { element: "#my-bookings-tappay-ccv", placeholder: "CCV" },
          },
          styles: {
            input: { "font-size": "15px", color: "#171512" },
            ":focus": { color: "#0b8a5b" },
            ".valid": { color: "#171512" },
            ".invalid": { color: "#dc2626" },
          },
        });
        return true;
      } catch {
        return false;
      }
    };

    if (tryMount()) return;
    const timer = window.setInterval(() => {
      if (tryMount()) window.clearInterval(timer);
    }, 100);
    return () => window.clearInterval(timer);
  }, [paymentBooking, paymentMethod, sdkReady]);

  const openPayment = (booking: MyBooking) => {
    if (booking.holdExpiresAt && new Date(booking.holdExpiresAt).getTime() <= Date.now()) {
      setError("此保留已逾期，請重新整理後重新建立訂位");
      void loadBookings();
      return;
    }
    setPaymentBooking(booking);
    setPaymentMethod("credit_card");
    setPaymentError("");
    setAllowDemoFallback(false);
  };

  const closePayment = () => {
    if (busyCode) return;
    setPaymentBooking(null);
    setPaymentError("");
    setAllowDemoFallback(false);
  };

  const openCancel = (booking: MyBooking) => {
    setError("");
    setCancelBooking(booking);
  };

  const closeCancel = () => {
    if (busyCode) return;
    setCancelBooking(null);
  };

  const completeDemoAuthorization = async () => {
    if (!paymentBooking) return;
    setBusyCode(paymentBooking.bookingCode);
    setError("");
    setPaymentError("");
    try {
      const response = await javaApi.payBookingWithTestCard(paymentBooking.bookingCode);
      if (!response.success) {
        setPaymentError(response.errorMsg ?? "Demo 授權失敗");
        return;
      }
      await loadBookings();
      setPaymentBooking(null);
      setAllowDemoFallback(false);
    } catch (err) {
      setPaymentError(err instanceof Error ? err.message : "Demo 授權失敗");
    } finally {
      setBusyCode(null);
    }
  };

  const confirmPayment = async () => {
    if (!paymentBooking) return;
    if (paymentBooking.holdExpiresAt && new Date(paymentBooking.holdExpiresAt).getTime() <= Date.now()) {
      setPaymentError("此保留已逾期，請重新建立訂位");
      await loadBookings();
      return;
    }
    setBusyCode(paymentBooking.bookingCode);
    setError("");
    setPaymentError("");

    if (paymentMethod === "credit_card") {
      if (!window.TPDirect?.card) {
        setPaymentError("TapPay SDK 尚未載入，請稍後再試");
        setBusyCode(null);
        return;
      }
      const status = window.TPDirect.card.getTappayFieldsStatus();
      if (!status.canGetPrime) {
        setPaymentError("請完整填寫 TapPay 測試卡資料");
        setBusyCode(null);
        return;
      }
      window.TPDirect.card.getPrime(async (result: any) => {
        if (result.status !== 0) {
          setPaymentError(`TapPay prime 取得失敗：${result.msg}`);
          setBusyCode(null);
          return;
        }
        try {
          const response = await javaApi.payBookingByPrime({
            prime: result.card.prime,
            amount: paymentBooking.depositTotal,
            bookingCode: paymentBooking.bookingCode,
          });
          if (!response.success) {
            setPaymentError(response.errorMsg ?? "付款失敗");
            setAllowDemoFallback(
              Boolean(response.errorMsg?.includes("TapPay sandbox IP")),
            );
            return;
          }
          await loadBookings();
          setPaymentBooking(null);
          setAllowDemoFallback(false);
        } catch (err) {
          setPaymentError(err instanceof Error ? err.message : "付款失敗");
        } finally {
          setBusyCode(null);
        }
      });
      return;
    }

    try {
      const response = await javaApi.payBookingWithTestCard(paymentBooking.bookingCode);
      if (!response.success) {
        setPaymentError(response.errorMsg ?? "付款失敗");
        return;
      }
      await loadBookings();
      setPaymentBooking(null);
      setAllowDemoFallback(false);
    } catch (err) {
      setPaymentError(err instanceof Error ? err.message : "付款失敗");
    } finally {
      setBusyCode(null);
    }
  };

  const confirmCancel = async () => {
    if (!cancelBooking) return;
    setBusyCode(cancelBooking.bookingCode);
    setError("");
    try {
      const response = await javaApi.cancelBooking(cancelBooking.bookingCode);
      if (!response.success) {
        setError(response.errorMsg ?? "取消訂位失敗");
      }
      await loadBookings();
      setCancelBooking(null);
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
                管理已保留、待付款、已付款與已取消的訂位。付款、取消與逾期都會同步更新店家的可訂容量。
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
              <p className="mt-1 text-sm text-zinc-500">付款完成後訂位成立；取消或逾期會釋放店家容量。</p>
            </div>
            <Button variant="outline" onClick={loadBookings} disabled={loading || (mounted && !isLoggedIn)}>
              重新整理
            </Button>
          </div>

          {mounted && !isLoggedIn ? (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 px-5 py-10 text-center">
              <p className="text-lg font-black text-amber-950">請先用 LINE 登入</p>
              <p className="mt-2 text-sm leading-6 text-amber-800">
                訂位紀錄會綁定 LINE 帳號；登入後才能查看、付款與取消。
              </p>
              <Button onClick={login} className="mt-5 rounded-full bg-emerald-700 hover:bg-emerald-800">
                用 LINE 登入
              </Button>
            </div>
          ) : error ? (
            <div className="mb-5 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">
              {error}
            </div>
          ) : null}

          {mounted && !isLoggedIn ? null : loading ? (
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
                const holdCountdown = formatHoldCountdown(booking.holdExpiresAt, nowMs);
                const expiredInUi = booking.status === "PENDING_PAYMENT" && holdCountdown === "已逾期";
                const canPay = booking.status === "PENDING_PAYMENT" && booking.needsDeposit && !expiredInUi;
                const canCancel = booking.status !== "CANCELED" && booking.status !== "EXPIRED";
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
                      <p className="text-sm text-zinc-500">
                        {booking.status === "PENDING_PAYMENT" && holdCountdown
                          ? `座位保留倒數 ${holdCountdown}，付款完成後訂位才成立。`
                          : status.helper}
                      </p>
                      <div className="flex flex-col gap-2 sm:flex-row">
                        {canPay ? (
                          <Button
                            onClick={() => openPayment(booking)}
                            disabled={busy}
                            className="rounded-full bg-[#0b8a5b] px-5 hover:bg-[#087a50]"
                          >
                            支付訂金
                          </Button>
                        ) : null}
                        {canCancel ? (
                          <Button
                            variant="outline"
                            onClick={() => openCancel(booking)}
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

      {paymentBooking ? (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/35 px-4 pb-4 pt-12 backdrop-blur-sm sm:items-center sm:py-6">
          <section className="max-h-[92dvh] w-full max-w-xl overflow-y-auto rounded-[1.5rem] border border-black/10 bg-white shadow-2xl">
            <div className="border-b border-zinc-200 bg-[#fffdf8] px-6 py-5">
              <button
                type="button"
                onClick={closePayment}
                className="mb-4 text-sm font-semibold text-zinc-500 hover:text-zinc-900"
              >
                返回訂位
              </button>
              <p className="text-2xl font-black">確認訂金付款</p>
              <p className="mt-2 text-sm text-zinc-500">
                {paymentBooking.shopName} · {formatDateTime(paymentBooking)} · {paymentBooking.people} 人
              </p>
              {paymentBooking.holdExpiresAt ? (
                <p className="mt-3 w-fit rounded-full bg-amber-100 px-3 py-1 text-sm font-bold text-amber-900">
                  座位保留倒數 {formatHoldCountdown(paymentBooking.holdExpiresAt, nowMs)}
                </p>
              ) : null}
              <p className="mt-4 text-3xl font-black text-[#0b8a5b]">
                NT$ {paymentBooking.depositTotal}
              </p>
            </div>

            <div className="space-y-5 px-6 py-5">
              <div>
                <p className="mb-3 text-sm font-black">選擇付款方式</p>
                <div className="grid gap-2">
                  {paymentMethods.map((method) => {
                    const active = paymentMethod === method.id;
                    return (
                      <button
                        key={method.id}
                        type="button"
                        onClick={() => {
                          setPaymentMethod(method.id);
                          setPaymentError("");
                        }}
                        className={`flex items-center justify-between rounded-2xl border px-4 py-3 text-left transition ${
                          active
                            ? "border-[#0b8a5b] bg-emerald-50"
                            : "border-zinc-200 bg-white hover:border-zinc-300"
                        }`}
                      >
                        <span>
                          <span className="block font-black">{method.label}</span>
                          <span className="mt-0.5 block text-xs text-zinc-500">{method.helper}</span>
                        </span>
                        <span
                          className={`rounded-full px-3 py-1 text-xs font-bold ${
                            method.id === "credit_card"
                              ? "bg-emerald-100 text-emerald-800"
                              : "bg-zinc-100 text-zinc-500"
                          }`}
                        >
                          {method.badge}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {paymentMethod === "credit_card" ? (
                <div className="rounded-2xl border border-zinc-200 bg-zinc-50 p-4">
                  <div className="mb-3 flex items-start justify-between gap-4">
                    <div>
                      <p className="text-sm font-black">TapPay Sandbox 信用卡</p>
                      <p className="mt-1 text-xs leading-5 text-zinc-500">
                        測試卡 4242 4242 4242 4242 / 任意未來日期 / CCV 123
                      </p>
                    </div>
                    <span className="rounded-full bg-white px-3 py-1 text-xs font-bold text-emerald-700">
                      取得 prime
                    </span>
                  </div>
                  <div className="grid gap-3">
                    <div>
                      <label className="text-sm font-semibold">卡號</label>
                      <div
                        id="my-bookings-tappay-number"
                        className="mt-1 h-11 rounded-xl border border-zinc-200 bg-white px-3 py-2"
                      />
                    </div>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <div>
                        <label className="text-sm font-semibold">有效期限</label>
                        <div
                          id="my-bookings-tappay-expiry"
                          className="mt-1 h-11 rounded-xl border border-zinc-200 bg-white px-3 py-2"
                        />
                      </div>
                      <div>
                        <label className="text-sm font-semibold">CCV</label>
                        <div
                          id="my-bookings-tappay-ccv"
                          className="mt-1 h-11 rounded-xl border border-zinc-200 bg-white px-3 py-2"
                        />
                      </div>
                    </div>
                  </div>
                  <p className="mt-3 text-xs leading-5 text-zinc-500">
                    信用卡會透過 TapPay sandbox iframe 取得 prime，再由後端呼叫 pay-by-prime。此為測試環境，不會產生真實扣款。
                  </p>
                </div>
              ) : (
                <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                  {paymentMethods.find((method) => method.id === paymentMethod)?.label} 目前為 demo 授權流程；production 需串接第三方錢包 redirect / SDK confirmation。
                </div>
              )}

              {paymentError ? (
                <div className="space-y-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  <p className="font-semibold">{paymentError}</p>
                  {allowDemoFallback ? (
                    <div className="rounded-xl border border-red-200 bg-white/75 p-3 text-xs leading-5 text-red-800">
                      <p>
                        目前已完成 TapPay iframe prime 取得；失敗點是 TapPay sandbox 後台尚未允許此 server IP 呼叫 pay-by-prime。
                      </p>
                      <p className="mt-1">
                        本地展示可先使用 demo 授權完成訂位；正式上線必須設定 TapPay 後台 IP 白名單。
                      </p>
                      <Button
                        type="button"
                        onClick={completeDemoAuthorization}
                        disabled={busyCode === paymentBooking.bookingCode}
                        className="mt-3 w-full bg-red-700 text-white hover:bg-red-800"
                      >
                        使用 demo 授權完成付款狀態
                      </Button>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>

            <div className="flex flex-col-reverse gap-3 border-t border-zinc-200 bg-white px-6 py-5 md:flex-row md:justify-end">
              <Button variant="outline" onClick={closePayment} disabled={busyCode === paymentBooking.bookingCode}>
                取消
              </Button>
              <Button
                onClick={confirmPayment}
                disabled={busyCode === paymentBooking.bookingCode}
                className="bg-[#0b8a5b] px-6 hover:bg-[#087a50]"
              >
                {busyCode === paymentBooking.bookingCode
                  ? "付款處理中..."
                  : paymentMethod === "credit_card"
                    ? "取得 TapPay prime 並付款"
                    : "確認 demo 授權付款"}
              </Button>
            </div>
          </section>
        </div>
      ) : null}

      {cancelBooking ? (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/35 px-4 pb-4 pt-12 backdrop-blur-sm sm:items-center sm:py-6">
          <section className="max-h-[92dvh] w-full max-w-lg overflow-y-auto rounded-[1.5rem] border border-black/10 bg-white shadow-2xl">
            <div className="border-b border-zinc-200 bg-[#fffdf8] px-6 py-5">
              <p className="text-sm font-bold uppercase tracking-[0.22em] text-red-600">Cancel reservation</p>
              <h2 className="mt-2 text-2xl font-black">確認取消訂位？</h2>
              <p className="mt-2 text-sm leading-6 text-zinc-500">
                取消後此訂位會標記為已取消，店家時段容量會立即釋放。此 demo 不處理退款流程。
              </p>
            </div>

            <div className="space-y-4 px-6 py-5">
              <div className="rounded-2xl border border-zinc-200 bg-[#fffdf8] p-4">
                <p className="text-lg font-black">{cancelBooking.shopName}</p>
                <p className="mt-1 font-mono text-sm text-zinc-500">{cancelBooking.bookingCode}</p>
                <div className="mt-4 grid gap-3 text-sm md:grid-cols-3">
                  <div>
                    <p className="text-xs font-bold uppercase tracking-widest text-zinc-400">時間</p>
                    <p className="mt-1 font-bold">{formatDateTime(cancelBooking)}</p>
                  </div>
                  <div>
                    <p className="text-xs font-bold uppercase tracking-widest text-zinc-400">人數</p>
                    <p className="mt-1 font-bold">{cancelBooking.people} 人</p>
                  </div>
                  <div>
                    <p className="text-xs font-bold uppercase tracking-widest text-zinc-400">狀態</p>
                    <p className="mt-1 font-bold">{statusCopy[cancelBooking.status].label}</p>
                  </div>
                </div>
              </div>

              <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-900">
                若這是已付款訂位，目前僅示範取消與容量釋放；正式產品需再接退款/取消政策。
              </div>
            </div>

            <div className="flex flex-col-reverse gap-3 border-t border-zinc-200 bg-white px-6 py-5 md:flex-row md:justify-end">
              <Button variant="outline" onClick={closeCancel} disabled={busyCode === cancelBooking.bookingCode}>
                保留訂位
              </Button>
              <Button
                onClick={confirmCancel}
                disabled={busyCode === cancelBooking.bookingCode}
                className="bg-red-700 px-6 text-white hover:bg-red-800"
              >
                {busyCode === cancelBooking.bookingCode ? "取消中..." : "確認取消並釋放容量"}
              </Button>
            </div>
          </section>
        </div>
      ) : null}
    </main>
  );
}
