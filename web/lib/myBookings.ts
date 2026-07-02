import type { CustomerTopUpAdjustment, MyBooking } from "@/lib/api";
import { formatCurrencyAbs } from "@/lib/money";

export type PaymentMethod = "credit_card" | "line_pay" | "apple_pay" | "jkopay";

export type RescheduleForm = {
  date: string;
  time: string;
  people: string;
  tableType: string;
};

export type FeedbackForm = {
  rating: 1 | 2 | 3;
  tags: string[];
  note: string;
  doNotRecommend: boolean;
};

export type IncidentForm = {
  incidentType: "RESTAURANT_DELAY" | "CUSTOMER_LATE";
  delayMinutes: string;
  message: string;
};

export const statusCopy: Record<MyBooking["status"], { label: string; tone: string; helper: string }> = {
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

export const paymentMethods: { id: PaymentMethod; label: string; helper: string; badge: string }[] = [
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

export const tableTypeOptions = [
  { value: "normal", label: "一般座位" },
  { value: "bar", label: "吧台" },
  { value: "private", label: "包廂" },
];

export const feedbackTagOptions = ["安靜", "份量大", "服務快", "太吵", "適合聚餐", "價格合理", "停車方便", "不再推薦"];

export function formatDateTime(booking: MyBooking) {
  return `${booking.date} ${booking.time}`;
}

export function currency(value: number) {
  return formatCurrencyAbs(value);
}

export function topUpBusyKey(adjustment: CustomerTopUpAdjustment) {
  return `TOPUP-${adjustment.id}`;
}

export function formatHoldCountdown(holdExpiresAt: string | null | undefined, nowMs: number) {
  if (!holdExpiresAt) return null;
  const remainingMs = new Date(holdExpiresAt).getTime() - nowMs;
  if (remainingMs <= 0) return "已逾期";
  const totalSeconds = Math.ceil(remainingMs / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}
