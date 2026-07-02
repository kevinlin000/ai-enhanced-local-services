"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { javaApi, type CustomerTopUpAdjustment, type DiningMemory, type MyBooking } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  currency,
  feedbackTagOptions,
  formatDateTime,
  formatHoldCountdown,
  paymentMethods,
  statusCopy,
  tableTypeOptions,
  topUpBusyKey,
  type FeedbackForm,
  type IncidentForm,
  type PaymentMethod,
  type RescheduleForm,
} from "@/lib/myBookings";

declare global {
  interface Window {
    TPDirect: any;
  }
}

export default function MyBookingsPage() {
  const { isLoggedIn, isAuthLoading, login, mounted } = useAuth();
  const [bookings, setBookings] = useState<MyBooking[]>([]);
  const [topUpAdjustments, setTopUpAdjustments] = useState<CustomerTopUpAdjustment[]>([]);
  const [memoryByBooking, setMemoryByBooking] = useState<Record<string, DiningMemory>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyCode, setBusyCode] = useState<string | null>(null);
  const [paymentBooking, setPaymentBooking] = useState<MyBooking | null>(null);
  const [topUpPayment, setTopUpPayment] = useState<CustomerTopUpAdjustment | null>(null);
  const [cancelBooking, setCancelBooking] = useState<MyBooking | null>(null);
  const [feedbackBooking, setFeedbackBooking] = useState<MyBooking | null>(null);
  const [feedbackForm, setFeedbackForm] = useState<FeedbackForm>({
    rating: 2,
    tags: ["安靜"],
    note: "",
    doNotRecommend: false,
  });
  const [feedbackError, setFeedbackError] = useState("");
  const [incidentBooking, setIncidentBooking] = useState<MyBooking | null>(null);
  const [incidentForm, setIncidentForm] = useState<IncidentForm>({
    incidentType: "CUSTOMER_LATE",
    delayMinutes: "15",
    message: "",
  });
  const [incidentError, setIncidentError] = useState("");
  const [rescheduleBooking, setRescheduleBooking] = useState<MyBooking | null>(null);
  const [rescheduleForm, setRescheduleForm] = useState<RescheduleForm>({
    date: "",
    time: "",
    people: "2",
    tableType: "normal",
  });
  const [rescheduleError, setRescheduleError] = useState("");
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("credit_card");
  const [paymentError, setPaymentError] = useState("");
  const [allowDemoFallback, setAllowDemoFallback] = useState(false);
  const [sdkReady, setSdkReady] = useState(false);
  const [nowMs, setNowMs] = useState(() => Date.now());

  const loadBookings = useCallback(async () => {
    if (mounted && isAuthLoading) {
      setLoading(true);
      return;
    }
    if (mounted && !isLoggedIn) {
      setBookings([]);
      setTopUpAdjustments([]);
      setMemoryByBooking({});
      setLoading(false);
      setError("");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const response = await javaApi.myBookings();
      if (!response.success) {
        setError(response.errorMsg ?? "讀取訂位失敗");
        setBookings([]);
        setTopUpAdjustments([]);
        setMemoryByBooking({});
      } else {
        setBookings(response.data ?? []);
        const topUpResponse = await javaApi.customerTopUpAdjustments().catch(() => null);
        if (topUpResponse?.success && topUpResponse.data?.adjustments) {
          setTopUpAdjustments(topUpResponse.data.adjustments);
        } else {
          setTopUpAdjustments([]);
        }
        const memoryResponse = await javaApi.myDiningMemory().catch(() => null);
        if (memoryResponse?.success && memoryResponse.data?.memories) {
          setMemoryByBooking(
            Object.fromEntries(
              memoryResponse.data.memories.map((memory) => [memory.bookingCode, memory]),
            ),
          );
        } else {
          setMemoryByBooking({});
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "讀取訂位失敗");
      setBookings([]);
      setTopUpAdjustments([]);
      setMemoryByBooking({});
    } finally {
      setLoading(false);
    }
  }, [isAuthLoading, isLoggedIn, mounted]);

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
    if ((!paymentBooking && !topUpPayment) || paymentMethod !== "credit_card" || !sdkReady) return;
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
  }, [paymentBooking, topUpPayment, paymentMethod, sdkReady]);

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

  const openTopUpPayment = (adjustment: CustomerTopUpAdjustment) => {
    setError("");
    setTopUpPayment(adjustment);
    setPaymentBooking(null);
    setPaymentMethod("credit_card");
    setPaymentError("");
    setAllowDemoFallback(false);
  };

  const closePayment = () => {
    if (busyCode) return;
    setPaymentBooking(null);
    setTopUpPayment(null);
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

  const openFeedback = (booking: MyBooking) => {
    const existing = memoryByBooking[booking.bookingCode];
    setError("");
    setFeedbackError("");
    setFeedbackBooking(booking);
    setFeedbackForm({
      rating: existing?.rating ?? 2,
      tags: existing?.tags?.length ? existing.tags : ["安靜"],
      note: existing?.note ?? "",
      doNotRecommend: Boolean(existing?.doNotRecommend),
    });
  };

  const closeFeedback = () => {
    if (busyCode) return;
    setFeedbackBooking(null);
    setFeedbackError("");
  };

  const openIncident = (booking: MyBooking) => {
    setError("");
    setIncidentError("");
    setIncidentBooking(booking);
    setIncidentForm({
      incidentType: "CUSTOMER_LATE",
      delayMinutes: "15",
      message: "",
    });
  };

  const closeIncident = () => {
    if (busyCode) return;
    setIncidentBooking(null);
    setIncidentError("");
  };

  const toggleFeedbackTag = (tag: string) => {
    setFeedbackForm((form) => {
      const exists = form.tags.includes(tag);
      const tags = exists ? form.tags.filter((item) => item !== tag) : [...form.tags, tag];
      return {
        ...form,
        tags,
        doNotRecommend: tag === "不再推薦" ? !exists : form.doNotRecommend,
      };
    });
  };

  const openReschedule = (booking: MyBooking) => {
    setError("");
    setRescheduleError("");
    setRescheduleBooking(booking);
    setRescheduleForm({
      date: booking.date,
      time: booking.time,
      people: String(booking.people),
      tableType: booking.tableType || "normal",
    });
  };

  const closeReschedule = () => {
    if (busyCode) return;
    setRescheduleBooking(null);
    setRescheduleError("");
  };

  const confirmReschedule = async () => {
    if (!rescheduleBooking) return;
    const people = Number.parseInt(rescheduleForm.people, 10);
    if (!rescheduleForm.date || !rescheduleForm.time || !Number.isFinite(people)) {
      setRescheduleError("請填寫日期、時間與人數");
      return;
    }
    if (people < 1 || people > 12) {
      setRescheduleError("人數需介於 1-12 人");
      return;
    }
    setBusyCode(rescheduleBooking.bookingCode);
    setError("");
    setRescheduleError("");
    try {
      const response = await javaApi.rescheduleBooking(rescheduleBooking.bookingCode, {
        date: rescheduleForm.date,
        time: rescheduleForm.time,
        people,
        tableType: rescheduleForm.tableType,
      });
      if (!response.success) {
        setRescheduleError(response.errorMsg ?? "改單失敗");
        return;
      }
      await loadBookings();
      setRescheduleBooking(null);
    } catch (err) {
      setRescheduleError(err instanceof Error ? err.message : "改單失敗");
    } finally {
      setBusyCode(null);
    }
  };

  const confirmFeedback = async () => {
    if (!feedbackBooking) return;
    const tags = [...feedbackForm.tags];
    if (feedbackForm.doNotRecommend && !tags.includes("不再推薦")) {
      tags.push("不再推薦");
    }
    if (tags.length === 0) {
      setFeedbackError("至少選擇 1 個標籤");
      return;
    }
    setBusyCode(feedbackBooking.bookingCode);
    setFeedbackError("");
    setError("");
    try {
      const response = await javaApi.saveDiningMemoryForBooking(feedbackBooking.bookingCode, {
        rating: feedbackForm.rating,
        tags,
        note: feedbackForm.note,
        doNotRecommend: feedbackForm.doNotRecommend,
      });
      if (!response.success) {
        setFeedbackError(response.errorMsg ?? "偏好記錄失敗");
        return;
      }
      setMemoryByBooking((current) => ({
        ...current,
        [feedbackBooking.bookingCode]: response.data,
      }));
      setFeedbackBooking(null);
    } catch (err) {
      setFeedbackError(err instanceof Error ? err.message : "偏好記錄失敗");
    } finally {
      setBusyCode(null);
    }
  };

  const confirmIncident = async () => {
    if (!incidentBooking) return;
    const delayMinutes = Number.parseInt(incidentForm.delayMinutes, 10);
    if (!Number.isFinite(delayMinutes) || delayMinutes < 1 || delayMinutes > 45) {
      setIncidentError("延誤分鐘需介於 1-45 分鐘");
      return;
    }
    setBusyCode(incidentBooking.bookingCode);
    setIncidentError("");
    setError("");
    try {
      const response = await javaApi.createBookingIncident(incidentBooking.bookingCode, {
        incidentType: incidentForm.incidentType,
        delayMinutes,
        message: incidentForm.message.trim() || undefined,
      });
      if (!response.success) {
        setIncidentError(response.errorMsg ?? "救場通知建立失敗");
        return;
      }
      await loadBookings();
      setIncidentBooking(null);
    } catch (err) {
      setIncidentError(err instanceof Error ? err.message : "救場通知建立失敗");
    } finally {
      setBusyCode(null);
    }
  };

  const acceptIncidentProposal = async (booking: MyBooking) => {
    const incident = booking.latestIncident;
    if (!incident?.id || incident.proposedChange?.status !== "PENDING") return;
    setBusyCode(booking.bookingCode);
    setError("");
    try {
      const response = await javaApi.acceptBookingIncidentProposal(booking.bookingCode, incident.id);
      if (!response.success) {
        setError(response.errorMsg ?? "替代時段確認失敗");
        return;
      }
      await loadBookings();
    } catch (err) {
      setError(err instanceof Error ? err.message : "替代時段確認失敗");
    } finally {
      setBusyCode(null);
    }
  };

  const declineIncidentProposal = async (booking: MyBooking) => {
    const incident = booking.latestIncident;
    if (!incident?.id || incident.proposedChange?.status !== "PENDING") return;
    setBusyCode(booking.bookingCode);
    setError("");
    try {
      const response = await javaApi.declineBookingIncidentProposal(booking.bookingCode, incident.id);
      if (!response.success) {
        setError(response.errorMsg ?? "替代時段回覆失敗");
        return;
      }
      await loadBookings();
    } catch (err) {
      setError(err instanceof Error ? err.message : "替代時段回覆失敗");
    } finally {
      setBusyCode(null);
    }
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
    const activeBooking = paymentBooking;
    const activeTopUp = topUpPayment;
    if (!activeBooking && !activeTopUp) return;

    if (activeBooking?.holdExpiresAt && new Date(activeBooking.holdExpiresAt).getTime() <= Date.now()) {
      setPaymentError("此保留已逾期，請重新建立訂位");
      await loadBookings();
      return;
    }
    const busyKey = activeTopUp ? topUpBusyKey(activeTopUp) : activeBooking!.bookingCode;
    setBusyCode(busyKey);
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
          const response = activeTopUp
            ? await javaApi.payTopUpByPrime({
                prime: result.card.prime,
                adjustmentId: activeTopUp.id,
              })
            : await javaApi.payBookingByPrime({
                prime: result.card.prime,
                amount: activeBooking!.depositTotal,
                bookingCode: activeBooking!.bookingCode,
              });
          if (!response.success) {
            setPaymentError(response.errorMsg ?? "付款失敗");
            setAllowDemoFallback(
              Boolean(activeBooking && response.errorMsg?.includes("TapPay sandbox IP")),
            );
            return;
          }
          await loadBookings();
          setPaymentBooking(null);
          setTopUpPayment(null);
          setAllowDemoFallback(false);
        } catch (err) {
          setPaymentError(err instanceof Error ? err.message : "付款失敗");
        } finally {
          setBusyCode(null);
        }
      });
      return;
    }

    if (activeTopUp) {
      setPaymentError("補款目前僅支援信用卡 TapPay checkout");
      setBusyCode(null);
      return;
    }

    try {
      const response = await javaApi.payBookingWithTestCard(activeBooking!.bookingCode);
      if (!response.success) {
        setPaymentError(response.errorMsg ?? "付款失敗");
        return;
      }
      await loadBookings();
      setPaymentBooking(null);
      setTopUpPayment(null);
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

  const activePaymentTarget = topUpPayment ?? paymentBooking;
  const activePaymentBusyKey = topUpPayment
    ? topUpBusyKey(topUpPayment)
    : paymentBooking?.bookingCode;
  const activePaymentAmount = topUpPayment
    ? Math.abs(Number(topUpPayment.deltaAmount ?? 0))
    : Number(paymentBooking?.depositTotal ?? 0);
  const activePaymentTitle = topUpPayment ? "確認訂金補款" : "確認訂金付款";
  const activePaymentSubtitle = topUpPayment
    ? `${topUpPayment.shopName} · ${topUpPayment.bookingCode} · 目標 ${topUpPayment.proposedDate} ${topUpPayment.proposedTime}`
    : paymentBooking
      ? `${paymentBooking.shopName} · ${formatDateTime(paymentBooking)} · ${paymentBooking.people} 人`
      : "";
  const activePaymentPrimaryText = topUpPayment ? "取得 TapPay prime 並補款" : "取得 TapPay prime 並付款";

  return (
    <main className="bb-premium-page min-h-screen px-4 py-8 text-foreground md:px-8">
      <section className="mx-auto max-w-5xl">
        <div className="flex flex-col gap-5 border-b bb-accent-rule pb-6 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="bb-page-kicker">
              ByteBites Reservations
            </p>
            <h1 className="mt-3 text-3xl font-semibold tracking-normal md:text-4xl">我的訂位</h1>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-muted-foreground md:text-base">
              管理已保留、待付款、已付款與已取消的訂位。付款、取消與逾期都會同步更新店家的可訂容量。
            </p>
          </div>
          <Link href="/ai">
            <Button variant="outline" className="rounded-lg border-[rgb(167_137_67_/_0.22)] bg-[rgb(255_253_248_/_0.72)] px-4">
              回 AI 訂位
            </Button>
          </Link>
        </div>

        <div className="bb-premium-surface mt-6 rounded-lg p-5 md:p-6">
          <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="text-xl font-medium">訂位紀錄</h2>
              <p className="mt-1 text-sm text-zinc-500">付款完成後訂位成立；取消或逾期會釋放店家容量。</p>
            </div>
            <Button variant="outline" onClick={loadBookings} disabled={loading || isAuthLoading || (mounted && !isLoggedIn)}>
              重新整理
            </Button>
          </div>

          {mounted && !isAuthLoading && !isLoggedIn ? (
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-5 py-10 text-center">
              <p className="text-lg font-medium text-amber-950">請先用 LINE 登入</p>
              <p className="mt-2 text-sm leading-6 text-amber-800">
                訂位紀錄會綁定 LINE 帳號；登入後才能查看、付款與取消。
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

          {mounted && !isAuthLoading && isLoggedIn && !loading && topUpAdjustments.length > 0 ? (
            <section className="mb-5 rounded-lg border border-sky-200 bg-sky-50/70 p-4">
              <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                <div>
                  <h3 className="text-base font-semibold text-sky-950">待補款改單</h3>
                  <p className="mt-1 text-sm leading-6 text-sky-800">
                    已付款訂位若改單造成訂金增加，先完成補款；店家確認後才會套用改單。
                  </p>
                </div>
                <span className="w-fit rounded-full bg-white px-3 py-1 text-sm font-semibold text-sky-800">
                  {topUpAdjustments.length} 筆
                </span>
              </div>
              <div className="mt-4 grid gap-3">
                {topUpAdjustments.map((adjustment) => {
                  const completed = adjustment.settlementStatus === "COMPLETED";
                  const busy = busyCode === topUpBusyKey(adjustment);
                  return (
                    <div
                      key={adjustment.id}
                      className="grid gap-3 rounded-lg border border-sky-200 bg-white p-4 md:grid-cols-[1fr_auto]"
                    >
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-bold text-amber-800">
                            補收訂金
                          </span>
                          <span className="rounded-full bg-sky-100 px-2.5 py-1 text-xs font-bold text-sky-800">
                            {completed ? "已補款，等待店家套用" : "待付款"}
                          </span>
                          <span className="font-mono text-xs font-semibold text-zinc-500">
                            {adjustment.bookingCode}
                          </span>
                        </div>
                        <p className="mt-2 text-lg font-semibold text-zinc-950">
                          需補款 {currency(adjustment.deltaAmount)}
                        </p>
                        <p className="mt-1 text-sm leading-6 text-zinc-600">
                          目標改單：{adjustment.proposedDate} {adjustment.proposedTime}，
                          {adjustment.proposedPeople} 人，訂金 {currency(adjustment.currentDepositTotal)} →{" "}
                          {currency(adjustment.proposedDepositTotal)}
                        </p>
                        {completed ? (
                          <p className="mt-1 truncate text-xs font-semibold text-emerald-700">
                            補款交易編號：{adjustment.settlementTransId || "-"}
                          </p>
                        ) : null}
                      </div>
                      <div className="flex items-center md:justify-end">
                        <Button
                          type="button"
                          onClick={() => openTopUpPayment(adjustment)}
                          disabled={completed || busy}
                          className="rounded-full bg-sky-700 px-5 text-white hover:bg-sky-800 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          {completed ? "已完成補款" : busy ? "補款中..." : "前往補款"}
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>
          ) : null}

          {mounted && !isAuthLoading && !isLoggedIn ? null : loading ? (
            <div className="rounded-lg border border-zinc-200 bg-zinc-50 px-5 py-10 text-center text-zinc-500">
              讀取訂位中...
            </div>
          ) : bookings.length === 0 ? (
            <div className="bb-empty-state rounded-lg px-5 py-10 text-center">
              <p className="text-lg font-medium">目前沒有訂位</p>
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
                const canReschedule = ["PENDING_PAYMENT", "PAID", "CONFIRMED"].includes(booking.status) && !expiredInUi;
                const canIncident = ["PENDING_PAYMENT", "PAID", "CONFIRMED"].includes(booking.status) && !expiredInUi;
                const canRecordMemory = booking.status === "PAID" || booking.status === "CONFIRMED";
                const memory = memoryByBooking[booking.bookingCode];
                const busy = busyCode === booking.bookingCode;

                return (
                  <article
                    key={booking.bookingCode}
                    className="overflow-hidden rounded-lg border border-[rgb(222_216_203_/_0.82)] bg-[rgb(255_253_248_/_0.88)]"
                  >
                    <div className="flex flex-col gap-4 border-b border-zinc-200 bg-white px-5 py-4 md:flex-row md:items-center md:justify-between">
                      <div>
                        <p className="text-lg font-medium">{booking.shopName}</p>
                        <p className="mt-1 font-mono text-sm text-zinc-500">{booking.bookingCode}</p>
                      </div>
                      <span className={`w-fit rounded-full border px-4 py-1.5 text-sm font-medium ${status.tone}`}>
                        {status.label}
                      </span>
                    </div>

                    <div className="grid gap-4 px-5 py-5 md:grid-cols-4">
                      <div>
                        <p className="text-xs font-medium uppercase tracking-normal text-zinc-400">時間</p>
                        <p className="mt-1 text-base font-medium">{formatDateTime(booking)}</p>
                      </div>
                      <div>
                        <p className="text-xs font-medium uppercase tracking-normal text-zinc-400">人數</p>
                        <p className="mt-1 text-base font-medium">{booking.people} 人</p>
                      </div>
                      <div>
                        <p className="text-xs font-medium uppercase tracking-normal text-zinc-400">訂金</p>
                        <p className="mt-1 text-base font-medium">
                          {booking.needsDeposit ? `NT$ ${booking.depositTotal}` : "免訂金"}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs font-medium uppercase tracking-normal text-zinc-400">交易編號</p>
                        <p className="mt-1 truncate font-mono text-sm font-medium">
                          {booking.paymentTransId ?? "-"}
                        </p>
                      </div>
                    </div>

                    <div className="flex flex-col gap-3 border-t border-zinc-200 bg-white px-5 py-4 md:flex-row md:items-center md:justify-between">
                      <div className="space-y-1 text-sm text-zinc-500">
                        <p>
                          {booking.status === "PENDING_PAYMENT" && holdCountdown
                            ? `座位保留倒數 ${holdCountdown}，付款完成後訂位才成立。`
                            : status.helper}
                        </p>
                        {memory ? (
                          <p className="text-emerald-700">
                            私人記憶：{memory.tags.slice(0, 4).join("、")}
                            {memory.doNotRecommend ? "；下次 AI 會避開" : ""}
                          </p>
                        ) : null}
                        {booking.latestIncident ? (
                          <div className="mt-2 rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-sky-900">
                            <p className="font-medium">{booking.latestIncident.title}</p>
                            <p className="mt-1 leading-5 text-sky-800">
                              {booking.latestIncident.customerMessage}
                            </p>
                            {booking.latestIncident.proposedChange?.status === "PENDING" ? (
                              <div className="mt-3 rounded-lg border border-emerald-200 bg-white px-3 py-2">
                                <p className="text-sm font-medium text-emerald-800">店家提出替代時段</p>
                                <p className="mt-1 text-sm text-zinc-700">
                                  {booking.latestIncident.proposedChange.date}{" "}
                                  {booking.latestIncident.proposedChange.time} ·{" "}
                                  {booking.latestIncident.proposedChange.people} 人
                                </p>
                                {booking.latestIncident.proposedChange.message ? (
                                  <p className="mt-1 text-xs leading-5 text-zinc-500">
                                    {booking.latestIncident.proposedChange.message}
                                  </p>
                                ) : null}
                                {booking.latestIncident.proposedChange.expiresAt ? (
                                  <p className="mt-1 text-xs text-zinc-500">
                                    有效至 {booking.latestIncident.proposedChange.expiresAt}
                                  </p>
                                ) : null}
                                <div className="mt-3 flex flex-wrap gap-2">
                                  <Button
                                    type="button"
                                    onClick={() => acceptIncidentProposal(booking)}
                                    disabled={busy}
                                    className="h-9 rounded-full bg-[#0b8a5b] px-4 text-sm hover:bg-[#087a50]"
                                  >
                                    {busy ? "確認中..." : "接受改到此時段"}
                                  </Button>
                                  <Button
                                    type="button"
                                    variant="outline"
                                    onClick={() => declineIncidentProposal(booking)}
                                    disabled={busy}
                                    className="h-9 rounded-full border-zinc-300 px-4 text-sm text-zinc-700 hover:bg-zinc-50"
                                  >
                                    拒絕此提案
                                  </Button>
                                </div>
                              </div>
                            ) : null}
                          </div>
                        ) : null}
                      </div>
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
                        {canReschedule ? (
                          <Button
                            variant="outline"
                            onClick={() => openReschedule(booking)}
                            disabled={busy}
                            className="rounded-full px-5"
                          >
                            {busy ? "處理中..." : "改時間"}
                          </Button>
                        ) : null}
                        {canRecordMemory ? (
                          <Button
                            variant="outline"
                            onClick={() => openFeedback(booking)}
                            disabled={busy}
                            className="rounded-full px-5"
                          >
                            {memory ? "更新標籤" : "吃後標籤"}
                          </Button>
                        ) : null}
                        {canIncident ? (
                          <Button
                            variant="outline"
                            onClick={() => openIncident(booking)}
                            disabled={busy}
                            className="rounded-full px-5"
                          >
                            臨場救場
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

      {activePaymentTarget ? (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/35 px-4 pb-4 pt-12 backdrop-blur-sm sm:items-center sm:py-6">
          <section className="max-h-[92dvh] w-full max-w-xl overflow-y-auto rounded-lg border border-black/10 bg-white">
            <div className="border-b border-zinc-200 bg-[#fffdf8] px-6 py-5">
              <button
                type="button"
                onClick={closePayment}
                className="mb-4 text-sm font-medium text-zinc-500 hover:text-zinc-900"
              >
                返回訂位
              </button>
              <p className="text-xl font-medium">{activePaymentTitle}</p>
              <p className="mt-2 text-sm text-zinc-500">
                {activePaymentSubtitle}
              </p>
              {paymentBooking?.holdExpiresAt ? (
                <p className="mt-3 w-fit rounded-full bg-amber-100 px-3 py-1 text-sm font-medium text-amber-900">
                  座位保留倒數 {formatHoldCountdown(paymentBooking.holdExpiresAt, nowMs)}
                </p>
              ) : null}
              <p className="mt-4 text-2xl font-medium text-[#0b8a5b]">
                {currency(activePaymentAmount)}
              </p>
              {topUpPayment ? (
                <p className="mt-2 text-sm leading-6 text-zinc-500">
                  補款完成後，店家會確認並套用改單。
                </p>
              ) : null}
            </div>

            <div className="space-y-5 px-6 py-5">
              <div>
                <p className="mb-3 text-sm font-medium">選擇付款方式</p>
                <div className="grid gap-2">
                  {paymentMethods.map((method) => {
                    const active = paymentMethod === method.id;
                    const disabled = Boolean(topUpPayment && method.id !== "credit_card");
                    return (
                      <button
                        key={method.id}
                        type="button"
                        disabled={disabled}
                        onClick={() => {
                          if (disabled) return;
                          setPaymentMethod(method.id);
                          setPaymentError("");
                        }}
                        className={`flex items-center justify-between rounded-lg border px-4 py-3 text-left transition ${
                          active
                            ? "border-[#0b8a5b] bg-emerald-50"
                            : "border-zinc-200 bg-white hover:border-zinc-300"
                        } ${disabled ? "cursor-not-allowed opacity-50" : ""}`}
                      >
                        <span>
                          <span className="block font-medium">{method.label}</span>
                          <span className="mt-0.5 block text-xs text-zinc-500">{method.helper}</span>
                        </span>
                        <span
                          className={`rounded-full px-3 py-1 text-xs font-medium ${
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
                <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-4">
                  <div className="mb-3 flex items-start justify-between gap-4">
                    <div>
                      <p className="text-sm font-medium">TapPay Sandbox 信用卡</p>
                      <p className="mt-1 text-xs leading-5 text-zinc-500">
                        測試卡 4242 4242 4242 4242 / 任意未來日期 / CCV 123
                      </p>
                    </div>
                    <span className="rounded-full bg-white px-3 py-1 text-xs font-medium text-emerald-700">
                      取得 prime
                    </span>
                  </div>
                  <div className="grid gap-3">
                    <div>
                      <label className="text-sm font-medium">卡號</label>
                      <div
                        id="my-bookings-tappay-number"
                        className="mt-1 h-11 rounded-xl border border-zinc-200 bg-white px-3 py-2"
                      />
                    </div>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <div>
                        <label className="text-sm font-medium">有效期限</label>
                        <div
                          id="my-bookings-tappay-expiry"
                          className="mt-1 h-11 rounded-xl border border-zinc-200 bg-white px-3 py-2"
                        />
                      </div>
                      <div>
                        <label className="text-sm font-medium">CCV</label>
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
                <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                  {paymentMethods.find((method) => method.id === paymentMethod)?.label} 目前為 demo 授權流程；production 需串接第三方錢包 redirect / SDK confirmation。
                </div>
              )}

              {paymentError ? (
                <div className="space-y-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  <p className="font-medium">{paymentError}</p>
                  {allowDemoFallback && paymentBooking ? (
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
                        disabled={busyCode === activePaymentBusyKey}
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
              <Button variant="outline" onClick={closePayment} disabled={busyCode === activePaymentBusyKey}>
                取消
              </Button>
              <Button
                onClick={confirmPayment}
                disabled={busyCode === activePaymentBusyKey}
                className="bg-[#0b8a5b] px-6 hover:bg-[#087a50]"
              >
                {busyCode === activePaymentBusyKey
                  ? "付款處理中..."
                  : paymentMethod === "credit_card"
                    ? activePaymentPrimaryText
                    : "確認 demo 授權付款"}
              </Button>
            </div>
          </section>
        </div>
      ) : null}

      {incidentBooking ? (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/35 px-4 pb-4 pt-12 backdrop-blur-sm sm:items-center sm:py-6">
          <section className="max-h-[92dvh] w-full max-w-lg overflow-y-auto rounded-lg border border-black/10 bg-white">
            <div className="border-b border-zinc-200 bg-[#fffdf8] px-6 py-5">
              <button
                type="button"
                onClick={closeIncident}
                className="mb-4 text-sm font-medium text-zinc-500 hover:text-zinc-900"
              >
                返回訂位
              </button>
              <p className="text-sm font-medium uppercase tracking-normal text-emerald-700">Rescue notice</p>
              <h2 className="mt-2 text-xl font-medium">臨場救場通知</h2>
              <p className="mt-2 text-sm leading-6 text-zinc-500">
                {incidentBooking.shopName} · {formatDateTime(incidentBooking)} · {incidentBooking.people} 人
              </p>
            </div>

            <div className="space-y-5 px-6 py-5">
              <div>
                <p className="mb-2 text-sm font-medium">事件類型</p>
                <div className="grid gap-2 sm:grid-cols-2">
                  {[
                    { value: "CUSTOMER_LATE" as const, label: "我會晚到", helper: "通知店家保留座位" },
                    { value: "RESTAURANT_DELAY" as const, label: "現場等候過久", helper: "請店家協助安排或改時段" },
                  ].map((item) => {
                    const active = incidentForm.incidentType === item.value;
                    return (
                      <button
                        key={item.value}
                        type="button"
                        onClick={() => setIncidentForm((form) => ({ ...form, incidentType: item.value }))}
                        className={`rounded-lg border px-4 py-3 text-left transition ${
                          active ? "border-emerald-700 bg-emerald-50 text-emerald-900" : "border-zinc-200 bg-white text-zinc-700"
                        }`}
                      >
                        <span className="block text-sm font-medium">{item.label}</span>
                        <span className="mt-1 block text-xs leading-5 text-zinc-500">{item.helper}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              <label className="text-sm font-medium">
                預估延誤分鐘
                <input
                  type="number"
                  min={1}
                  max={45}
                  value={incidentForm.delayMinutes}
                  onChange={(event) => setIncidentForm((form) => ({ ...form, delayMinutes: event.target.value }))}
                  className="mt-1 h-11 w-full rounded-lg border border-zinc-200 bg-white px-3 text-sm outline-none focus:border-emerald-600"
                />
              </label>

              <label className="text-sm font-medium">
                自訂訊息
                <textarea
                  value={incidentForm.message}
                  onChange={(event) => setIncidentForm((form) => ({ ...form, message: event.target.value }))}
                  rows={3}
                  maxLength={500}
                  className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm leading-6 outline-none focus:border-emerald-600"
                  placeholder={
                    incidentForm.incidentType === "CUSTOMER_LATE"
                      ? "例如：我塞車會晚 15 分鐘，麻煩保留座位。"
                      : "例如：現場等候超過 15 分鐘，想請店家協助安排。"
                  }
                />
              </label>

              <div className="rounded-lg border border-sky-200 bg-sky-50 px-4 py-3 text-sm leading-6 text-sky-900">
                建立後會同步給店家後台；店家可保留座位、提出替代時段，並透過 LINE 回覆你。
              </div>

              {incidentError ? (
                <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700">
                  {incidentError}
                </div>
              ) : null}
            </div>

            <div className="flex flex-col-reverse gap-3 border-t border-zinc-200 bg-white px-6 py-5 md:flex-row md:justify-end">
              <Button variant="outline" onClick={closeIncident} disabled={busyCode === incidentBooking.bookingCode}>
                取消
              </Button>
              <Button
                onClick={confirmIncident}
                disabled={busyCode === incidentBooking.bookingCode}
                className="bg-[#0b8a5b] px-6 hover:bg-[#087a50]"
              >
                {busyCode === incidentBooking.bookingCode ? "通知中..." : "建立救場通知"}
              </Button>
            </div>
          </section>
        </div>
      ) : null}

      {feedbackBooking ? (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/35 px-4 pb-4 pt-12 backdrop-blur-sm sm:items-center sm:py-6">
          <section className="max-h-[92dvh] w-full max-w-lg overflow-y-auto rounded-lg border border-black/10 bg-white">
            <div className="border-b border-zinc-200 bg-[#fffdf8] px-6 py-5">
              <button
                type="button"
                onClick={closeFeedback}
                className="mb-4 text-sm font-medium text-zinc-500 hover:text-zinc-900"
              >
                返回訂位
              </button>
              <p className="text-sm font-medium uppercase tracking-normal text-emerald-700">Private memory</p>
              <h2 className="mt-2 text-xl font-medium">記錄這次用餐</h2>
              <p className="mt-2 text-sm leading-6 text-zinc-500">
                {feedbackBooking.shopName} · {formatDateTime(feedbackBooking)} · {feedbackBooking.people} 人
              </p>
            </div>

            <div className="space-y-5 px-6 py-5">
              <div>
                <p className="mb-2 text-sm font-medium">下次還會想來嗎？</p>
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { value: 1 as const, label: "避開" },
                    { value: 2 as const, label: "普通" },
                    { value: 3 as const, label: "會再訪" },
                  ].map((item) => {
                    const active = feedbackForm.rating === item.value;
                    return (
                      <button
                        key={item.value}
                        type="button"
                        onClick={() => setFeedbackForm((form) => ({ ...form, rating: item.value }))}
                        className={`h-11 rounded-lg border text-sm font-medium transition ${
                          active ? "border-emerald-700 bg-emerald-50 text-emerald-800" : "border-zinc-200 bg-white text-zinc-700"
                        }`}
                      >
                        {item.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div>
                <p className="mb-2 text-sm font-medium">私人標籤</p>
                <div className="flex flex-wrap gap-2">
                  {feedbackTagOptions.map((tag) => {
                    const active = feedbackForm.tags.includes(tag);
                    return (
                      <button
                        key={tag}
                        type="button"
                        onClick={() => toggleFeedbackTag(tag)}
                        className={`rounded-full border px-3 py-2 text-sm font-medium transition ${
                          active ? "border-emerald-700 bg-emerald-50 text-emerald-800" : "border-zinc-200 bg-white text-zinc-600"
                        }`}
                      >
                        {tag}
                      </button>
                    );
                  })}
                </div>
              </div>

              <label className="flex items-start gap-3 rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-3 text-sm">
                <input
                  type="checkbox"
                  checked={feedbackForm.doNotRecommend}
                  onChange={(event) =>
                    setFeedbackForm((form) => ({
                      ...form,
                      doNotRecommend: event.target.checked,
                      tags: event.target.checked && !form.tags.includes("不再推薦")
                        ? [...form.tags, "不再推薦"]
                        : form.tags.filter((tag) => event.target.checked || tag !== "不再推薦"),
                    }))
                  }
                  className="mt-1"
                />
                <span>
                  <span className="block font-medium text-zinc-900">下次不要再推薦這家</span>
                  <span className="mt-1 block leading-5 text-zinc-500">只影響你的私人 AI 推薦，不會公開顯示。</span>
                </span>
              </label>

              <label className="text-sm font-medium">
                給下次自己的備註
                <textarea
                  value={feedbackForm.note}
                  onChange={(event) => setFeedbackForm((form) => ({ ...form, note: event.target.value }))}
                  rows={3}
                  maxLength={500}
                  className="mt-1 w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm leading-6 outline-none focus:border-emerald-600"
                  placeholder="例如：靠窗位偏吵，下次排內側。"
                />
              </label>

              {feedbackError ? (
                <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700">
                  {feedbackError}
                </div>
              ) : null}
            </div>

            <div className="flex flex-col-reverse gap-3 border-t border-zinc-200 bg-white px-6 py-5 md:flex-row md:justify-end">
              <Button variant="outline" onClick={closeFeedback} disabled={busyCode === feedbackBooking.bookingCode}>
                取消
              </Button>
              <Button
                onClick={confirmFeedback}
                disabled={busyCode === feedbackBooking.bookingCode}
                className="bg-[#0b8a5b] px-6 hover:bg-[#087a50]"
              >
                {busyCode === feedbackBooking.bookingCode ? "記錄中..." : "儲存私人記憶"}
              </Button>
            </div>
          </section>
        </div>
      ) : null}

      {rescheduleBooking ? (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/35 px-4 pb-4 pt-12 backdrop-blur-sm sm:items-center sm:py-6">
          <section className="max-h-[92dvh] w-full max-w-lg overflow-y-auto rounded-lg border border-black/10 bg-white">
            <div className="border-b border-zinc-200 bg-[#fffdf8] px-6 py-5">
              <button
                type="button"
                onClick={closeReschedule}
                className="mb-4 text-sm font-medium text-zinc-500 hover:text-zinc-900"
              >
                返回訂位
              </button>
              <p className="text-sm font-medium uppercase tracking-normal text-emerald-700">Reschedule</p>
              <h2 className="mt-2 text-xl font-medium">修改訂位時間</h2>
              <p className="mt-2 text-sm leading-6 text-zinc-500">
                {rescheduleBooking.shopName} · {rescheduleBooking.bookingCode}
              </p>
            </div>

            <div className="space-y-5 px-6 py-5">
              <div className="rounded-lg border border-zinc-200 bg-[#fffdf8] p-4 text-sm">
                <p className="font-medium">目前訂位</p>
                <p className="mt-2 text-zinc-600">
                  {formatDateTime(rescheduleBooking)} · {rescheduleBooking.people} 人 ·{" "}
                  {tableTypeOptions.find((item) => item.value === rescheduleBooking.tableType)?.label ?? "一般座位"}
                </p>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <label className="text-sm font-medium">
                  日期
                  <input
                    type="date"
                    value={rescheduleForm.date}
                    onChange={(event) => setRescheduleForm((form) => ({ ...form, date: event.target.value }))}
                    className="mt-1 h-11 w-full rounded-lg border border-zinc-200 bg-white px-3 text-sm outline-none focus:border-emerald-600"
                  />
                </label>
                <label className="text-sm font-medium">
                  時間
                  <input
                    type="time"
                    value={rescheduleForm.time}
                    onChange={(event) => setRescheduleForm((form) => ({ ...form, time: event.target.value }))}
                    className="mt-1 h-11 w-full rounded-lg border border-zinc-200 bg-white px-3 text-sm outline-none focus:border-emerald-600"
                  />
                </label>
                <label className="text-sm font-medium">
                  人數
                  <input
                    type="number"
                    min={1}
                    max={12}
                    value={rescheduleForm.people}
                    onChange={(event) => setRescheduleForm((form) => ({ ...form, people: event.target.value }))}
                    className="mt-1 h-11 w-full rounded-lg border border-zinc-200 bg-white px-3 text-sm outline-none focus:border-emerald-600"
                  />
                </label>
                <label className="text-sm font-medium">
                  座位
                  <select
                    value={rescheduleForm.tableType}
                    onChange={(event) => setRescheduleForm((form) => ({ ...form, tableType: event.target.value }))}
                    className="mt-1 h-11 w-full rounded-lg border border-zinc-200 bg-white px-3 text-sm outline-none focus:border-emerald-600"
                  >
                    {tableTypeOptions.map((item) => (
                      <option key={item.value} value={item.value}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              {rescheduleError ? (
                <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700">
                  {rescheduleError}
                </div>
              ) : null}
            </div>

            <div className="flex flex-col-reverse gap-3 border-t border-zinc-200 bg-white px-6 py-5 md:flex-row md:justify-end">
              <Button variant="outline" onClick={closeReschedule} disabled={busyCode === rescheduleBooking.bookingCode}>
                取消
              </Button>
              <Button
                onClick={confirmReschedule}
                disabled={busyCode === rescheduleBooking.bookingCode}
                className="bg-[#0b8a5b] px-6 hover:bg-[#087a50]"
              >
                {busyCode === rescheduleBooking.bookingCode ? "改單中..." : "確認改單"}
              </Button>
            </div>
          </section>
        </div>
      ) : null}

      {cancelBooking ? (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/35 px-4 pb-4 pt-12 backdrop-blur-sm sm:items-center sm:py-6">
          <section className="max-h-[92dvh] w-full max-w-lg overflow-y-auto rounded-lg border border-black/10 bg-white">
            <div className="border-b border-zinc-200 bg-[#fffdf8] px-6 py-5">
              <p className="text-sm font-medium uppercase tracking-normal text-red-600">Cancel reservation</p>
              <h2 className="mt-2 text-xl font-medium">確認取消訂位？</h2>
              <p className="mt-2 text-sm leading-6 text-zinc-500">
                取消後此訂位會標記為已取消，店家時段容量會立即釋放。此 demo 不處理退款流程。
              </p>
            </div>

            <div className="space-y-4 px-6 py-5">
              <div className="rounded-lg border border-zinc-200 bg-[#fffdf8] p-4">
                <p className="text-lg font-medium">{cancelBooking.shopName}</p>
                <p className="mt-1 font-mono text-sm text-zinc-500">{cancelBooking.bookingCode}</p>
                <div className="mt-4 grid gap-3 text-sm md:grid-cols-3">
                  <div>
                    <p className="text-xs font-medium uppercase tracking-normal text-zinc-400">時間</p>
                    <p className="mt-1 font-medium">{formatDateTime(cancelBooking)}</p>
                  </div>
                  <div>
                    <p className="text-xs font-medium uppercase tracking-normal text-zinc-400">人數</p>
                    <p className="mt-1 font-medium">{cancelBooking.people} 人</p>
                  </div>
                  <div>
                    <p className="text-xs font-medium uppercase tracking-normal text-zinc-400">狀態</p>
                    <p className="mt-1 font-medium">{statusCopy[cancelBooking.status].label}</p>
                  </div>
                </div>
              </div>

              <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-900">
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
