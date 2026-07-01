import type {
  MerchantRefundNotificationPolicy,
  MerchantShop,
  MerchantSlot,
} from "@/lib/api";
import { formatCurrencyAbs } from "@/lib/money";

export function addDaysIso(days: number) {
  const value = new Date(Date.now() + days * 24 * 60 * 60 * 1000);
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Taipei",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  })
    .formatToParts(value)
    .reduce<Record<string, string>>((acc, part) => {
      acc[part.type] = part.value;
      return acc;
    }, {});
  return `${parts.year}-${parts.month}-${parts.day}`;
}

export const MIN_BOOKING_DATE = addDaysIso(1);

export const DEFAULT_DEMO_SHOP_PRIORITY = [10673, 10709, 10113, 10108, 10115, 10102, 10116];

export const DEMO_STORY_BY_SHOP_ID: Record<number, { label: string; detail: string }> = {
  10673: { label: "Story 1", detail: "大安部門聚餐" },
  10709: { label: "Story 1", detail: "大安部門聚餐" },
  10404: { label: "Story 1", detail: "大安候位測試" },
  10610: { label: "Story 1", detail: "大安聚餐" },
  10701: { label: "Story 1", detail: "大安熱門候位" },
  10113: { label: "Story 2", detail: "信義家庭開車" },
  10108: { label: "Story 2", detail: "信義家庭聚餐" },
  10598: { label: "Story 2", detail: "信義家庭用餐" },
  10225: { label: "Story 2", detail: "信義親子聚餐" },
  10111: { label: "Story 2", detail: "信義家庭聚餐" },
  10115: { label: "訂位 Demo", detail: "信義火鍋" },
  10102: { label: "停車 Demo", detail: "信義火鍋" },
  10116: { label: "候位 Demo", detail: "酸菜魚" },
};

export type MerchantSection = "overview" | "incidents" | "deposits" | "slots" | "flashDeals" | "shops";

export const MERCHANT_SECTION_COPY: Record<MerchantSection, { label: string; description: string }> = {
  overview: {
    label: "營運指揮台",
    description: "先處理會阻塞訂位、付款與通知同步的事項，再檢查容量、餐券與店家設定。",
  },
  incidents: {
    label: "工作佇列",
    description: "處理顧客晚到、現場等候過久與替代時段提案。",
  },
  deposits: {
    label: "訂金退款",
    description: "處理改單造成的補款、退款與人工確認。",
  },
  slots: {
    label: "時段容量",
    description: "調整可接待人數，直接影響 Web / LINE 訂位庫存。",
  },
  flashDeals: {
    label: "限時餐券",
    description: "管理離峰補位活動、限量庫存、已搶訂單與可售營收。",
  },
  shops: {
    label: "店家清單",
    description: "切換 demo 店家並查看故事標籤。",
  },
};

export const MERCHANT_SECTION_EVENT = "bytebites:merchant-section-change";

export function merchantSectionFromHash(hash: string): MerchantSection {
  if (hash === "#incident-queue") return "incidents";
  if (hash === "#deposit-queue") return "deposits";
  if (hash === "#slots") return "slots";
  if (hash === "#flash-deals") return "flashDeals";
  if (hash === "#shops") return "shops";
  return "overview";
}

export const INCIDENT_TYPE_LABEL: Record<string, string> = {
  CUSTOMER_LATE: "顧客晚到",
  RESTAURANT_DELAY: "顧客現場等候",
};

export const BOOKING_STATUS_LABEL: Record<string, string> = {
  PENDING_PAYMENT: "待付款",
  PAID: "已付款",
  CONFIRMED: "已確認",
  CANCELED: "已取消",
  EXPIRED: "已逾期",
  UNKNOWN: "未知",
};

export const ADJUSTMENT_TYPE_LABEL: Record<string, string> = {
  TOP_UP: "補收訂金",
  REFUND: "退還訂金",
};

export const ADJUSTMENT_SOURCE_LABEL: Record<string, string> = {
  CUSTOMER_RESCHEDULE: "顧客改單",
  INCIDENT_PROPOSAL: "救場提案",
};

export const SETTLEMENT_STATUS_LABEL: Record<string, string> = {
  PENDING: "等待處理",
  PROCESSING: "處理中",
  COMPLETED: "金流完成",
  FAILED: "退款失敗",
};

export const REFUND_REPORT_ACTION_LABEL: Record<string, string> = {
  ESCALATE_FAILED_REFUNDS: "先處理失敗退款",
  ESCALATE_STUCK_REFUNDS: "先處理逾時退款",
  FOLLOW_UP_ESCALATED_REFUNDS: "追蹤人工處理退款",
  NO_REFUND_ACTION: "無需跟進",
};

export function demoStoryForShop(shop: MerchantShop) {
  return DEMO_STORY_BY_SHOP_ID[shop.id] ?? null;
}

export function slotHealth(slot: MerchantSlot) {
  if (slot.capacity === 0) return { label: "關閉", tone: "bg-stone-100 text-stone-600" };
  if (slot.remaining === 0) return { label: "額滿", tone: "bg-red-50 text-red-700" };
  if (slot.remaining <= 2) return { label: "快滿", tone: "bg-amber-50 text-amber-700" };
  return { label: "開放", tone: "bg-emerald-50 text-emerald-700" };
}

export function currency(value: number) {
  return formatCurrencyAbs(value);
}

export function voucherCurrency(value: number) {
  return currency(Math.round(Number(value ?? 0) / 100));
}

export function settlementTone(status: string) {
  if (status === "COMPLETED") return "bg-emerald-100 text-emerald-800";
  if (status === "FAILED") return "bg-red-100 text-red-700";
  if (status === "PROCESSING") return "bg-amber-100 text-amber-800";
  return "bg-white text-sky-800";
}

export function refundReportTone(status: string) {
  if (status === "ACTION_REQUIRED") return "border-red-100 bg-red-50 text-red-800";
  if (status === "FOLLOW_UP") return "border-amber-100 bg-amber-50 text-amber-800";
  return "border-emerald-100 bg-emerald-50 text-emerald-800";
}

export function refundReasonLabel(reason?: string) {
  if (reason === "FAILED_REFUND") return "退款失敗";
  if (reason === "STUCK_PROCESSING") return "逾時未完成";
  return "退款注意";
}

export function refundHeadlineCopy(headline?: string) {
  return (headline || "")
    .replaceAll("升級處理", "人工確認")
    .replaceAll("未升級", "待人工確認")
    .replaceAll("已升級", "已人工確認")
    .replaceAll("未回寫", "未完成");
}

export function refundNotificationPolicyLabel(policy: MerchantRefundNotificationPolicy | null) {
  if (!policy) return "";
  if (policy.shouldNotify) return "可通知營運";
  if (policy.reason === "COOLDOWN_ACTIVE") return "剛通知過，暫不重送";
  if (policy.reason === "NO_REFUND_ATTENTION") return "無需通知";
  if (policy.reason === "MISSING_SHOP") return "缺少店家資訊";
  return policy.reason;
}
