"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  Bell,
  CalendarCheck,
  CheckCircle2,
  CircleDashed,
  CreditCard,
  Heart,
  Loader2,
  Search,
  Sparkles,
  Trash2,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { javaApi } from "@/lib/api";
import { streamAgentResponse, type AgentTransaction } from "@/lib/agentStream";
import { useAuth } from "@/lib/auth";
import { AgentShopCard, type AgentShop } from "@/components/AgentShopCard";
import { MarkdownMessage } from "@/components/MarkdownMessage";

const AI_API = "";

interface Msg {
  role: "user" | "ai";
  content: string;
  toolsUsed?: string[];
  toolSteps?: ToolStep[];
  statusLabel?: string;
  streamMode?: "legacy" | "lifecycle";
  finalEventHandled?: boolean;
  done?: boolean;
  shops?: AgentShop[];
  transaction?: AgentTransaction;
}

type ToolStepStatus = "active" | "done";

type ToolStep = {
  name: string;
  label: string;
  status: ToolStepStatus;
};

type TableReviewInsights = {
  selectedReviews?: {
    rating?: number;
    text?: string;
    labels?: string[];
  }[];
  totalReviews?: number;
  nonEmptyReviews?: number;
};

const PRESETS = [
  "信義區想吃火鍋",
  "推薦大安區美式漢堡",
  "幫我訂辛殿麻辣鍋明天晚上 7 點 2 人",
  "中山站附近適合約會的高級餐廳",
];

const PRODUCT_HINTS = [
  { label: "AI 推薦", icon: Sparkles },
  { label: "可直接訂位", icon: CalendarCheck },
  { label: "額滿可等通知", icon: Bell },
  { label: "可收藏回訪", icon: Heart },
];

const TOOL_LABELS: Record<string, string> = {
  search_shops_by_mrt: "搜尋捷運附近",
  semantic_shop_search: "比對餐廳資料",
  create_hot_seat_order: "建立 Hot Seat 訂單",
  create_booking: "檢查並建立訂位",
  pay_booking_with_test_card: "確認訂金付款",
};

const STATUS_LABELS = {
  agent_start: "準備處理需求",
  turn_start: "正在理解你的需求",
  tool_execution_start: "正在查詢資料",
  tool_execution_end: "資料已取得，正在整理",
  message_update: "正在撰寫回覆",
  agent_end: "已完成",
  agent_error: "處理失敗",
} as const;

function toolLabel(name: string): string {
  return TOOL_LABELS[name] ?? name.replace(/_/g, " ");
}

function upsertToolStep(
  steps: ToolStep[] | undefined,
  name: string,
  status: ToolStepStatus,
): ToolStep[] {
  const next = [...(steps ?? [])];
  const existingIndex = next.findIndex((step) => step.name === name);
  const item = { name, label: toolLabel(name), status };
  if (existingIndex >= 0) {
    next[existingIndex] = item;
  } else {
    next.push(item);
  }
  return next;
}

function uniqueTools(tools: string[] | undefined, name: string): string[] {
  return [...new Set([...(tools ?? []), name])];
}

function shopId(shop: AgentShop): number {
  return Number(shop.shop_id ?? (shop as unknown as { id?: number | string }).id);
}

function normalizeAgentShop(shop: AgentShop): AgentShop | null {
  const id = shopId(shop);
  if (!Number.isFinite(id)) return null;
  const raw = shop as unknown as {
    avgPrice?: number | null;
    mrtStation?: string | null;
  };
  return {
    ...shop,
    shop_id: id,
    mrt_station: shop.mrt_station ?? raw.mrtStation ?? null,
    avg_price: shop.avg_price ?? raw.avgPrice ?? null,
    price_per_person:
      shop.price_per_person ??
      (raw.avgPrice != null ? `NT$ ${raw.avgPrice}` : null),
  };
}

function selectRecommendedShops(
  shops: AgentShop[] | undefined,
  recommendedShopIds: number[] | undefined,
): AgentShop[] | undefined {
  if (!shops || !recommendedShopIds?.length) return undefined;
  const normalized = shops
    .map(normalizeAgentShop)
    .filter((shop): shop is AgentShop => Boolean(shop));
  const byId = new Map(normalized.map((shop) => [shopId(shop), shop]));
  return recommendedShopIds
    .map((id) => byId.get(Number(id)))
    .filter((shop): shop is AgentShop => Boolean(shop));
}

function shopRaw(shop: AgentShop) {
  return shop as unknown as {
    category?: string | null;
    comments?: number | null;
    distance?: number | null;
  };
}

function cleanComparisonText(value?: string | null): string {
  return (value ?? "").replace(/\s+/g, " ").trim();
}

function shortComparisonText(value: string, limit = 58): string {
  const cleaned = cleanComparisonText(value).replace(/[。！？!]+$/g, "");
  if (cleaned.length <= limit) return cleaned;
  const clipped = cleaned.slice(0, limit);
  const cut = Math.max(clipped.lastIndexOf("，"), clipped.lastIndexOf("、"), clipped.lastIndexOf("；"));
  return `${(cut > 18 ? clipped.slice(0, cut) : clipped).replace(/[，、；]+$/g, "")}...`;
}

function usefulReviews(insights?: TableReviewInsights | null) {
  return (insights?.selectedReviews ?? [])
    .filter((review) => (review.rating ?? 0) >= 4 && cleanComparisonText(review.text))
    .slice(0, 3);
}

function hasRichComparisonData(shop: AgentShop, insights?: TableReviewInsights | null): boolean {
  return Boolean(
    cleanComparisonText(shop.ai_summary) ||
      (shop.signature_dishes?.length ?? 0) > 0 ||
      (shop.atmosphere_tags?.length ?? 0) > 0 ||
      usefulReviews(insights).length > 0,
  );
}

function formatFeatureHighlight(shop: AgentShop, insights?: TableReviewInsights | null): string {
  const dishes = (shop.signature_dishes ?? []).filter(Boolean).slice(0, 3);
  if (dishes.length > 0) return `招牌：${dishes.join("、")}`;

  const reviews = usefulReviews(insights);
  const labelCounts = new Map<string, number>();
  for (const review of reviews) {
    for (const label of review.labels ?? []) {
      if (["訂位", "上菜"].includes(label)) continue;
      labelCounts.set(label, (labelCounts.get(label) ?? 0) + 1);
    }
  }
  const labels = [...labelCounts.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([label]) => label)
    .slice(0, 2);
  if (labels.length > 0) return `評論亮點：${labels.join("、")}`;

  const reviewText = cleanComparisonText(reviews[0]?.text);
  if (reviewText) return shortComparisonText(reviewText);

  const summary = cleanComparisonText(shop.ai_summary);
  if (summary) return shortComparisonText(summary);

  const raw = shopRaw(shop);
  if ((raw.comments ?? 0) >= 500) return `Google 評論量 ${raw.comments} 則，可先作為人氣參考`;
  return "資料較少：目前只有基本店名、地點與價位，建議先看 Google Maps 或電話確認";
}

function formatBestFor(shop: AgentShop, insights?: TableReviewInsights | null): string {
  const tags = (shop.atmosphere_tags ?? []).filter(Boolean).slice(0, 2);
  if (tags.length > 0) return tags.join("、");

  const text = [
    shop.name,
    shopRaw(shop).category,
    shop.ai_summary,
    ...usefulReviews(insights).map((review) => review.text ?? ""),
  ]
    .join(" ")
    .toLowerCase();

  if (/火鍋|麻辣|鍋底|鴛鴦鍋/.test(text)) return "多人聚餐、想吃鍋物";
  if (/漢堡|burger|美式/.test(text)) return "朋友聚餐、想吃美式漢堡";
  if (/牛肉麵|麵|小吃/.test(text)) return "快速午晚餐、一人用餐";
  if (/家庭|長輩|親子|小孩/.test(text)) return "家庭聚餐、長輩同行";
  if (/商務|包廂|正式|宴客/.test(text)) return "商務聚餐、正式宴客";
  if (/約會|氣氛|浪漫|安靜/.test(text)) return "約會、安靜聊天";
  if ((shop.avg_price ?? 0) <= 300) return "快速簡餐、預算友善";
  return hasRichComparisonData(shop, insights) ? "朋友聚餐、一般正餐" : "需先確認資料完整度";
}

function formatOnlineBookingStatus(shop: AgentShop, insights?: TableReviewInsights | null): string {
  if ((shop.hot_seat_vouchers?.length ?? 0) > 0) return "Hot Seat 可搶";
  if (!hasRichComparisonData(shop, insights)) return "可線上訂位，但資料較少";
  const booking = shop.booking_difficulty ?? "";
  if (booking.includes("預約困難")) return "可線上訂位，建議提前";
  if (booking.includes("現場可入")) return "可線上訂位；通常也可現場";
  if (booking.includes("未提及")) return "可線上訂位，建議確認";
  return booking || "可線上訂位";
}

function formatComparisonMeta(shop: AgentShop): string {
  const raw = shop as unknown as {
    distance?: number | null;
  };
  const price = shop.price_per_person ?? (shop.avg_price != null ? `NT$ ${shop.avg_price}` : "");
  const location = [
    shop.district,
    shop.mrt_station ? `捷運${shop.mrt_station}` : null,
    raw.distance != null ? `${Math.round(raw.distance)}m` : null,
  ]
    .filter(Boolean)
    .join(" · ");
  return [price, location].filter(Boolean).join(" · ");
}

function AgentShopComparisonTable({ shops }: { shops: AgentShop[] }) {
  const [insightsByShop, setInsightsByShop] = useState<Record<number, TableReviewInsights | null>>({});
  const shopIdsKey = shops.map((shop) => shop.shop_id).join(",");

  useEffect(() => {
    if (!shopIdsKey) return;
    let canceled = false;
    const ids = shopIdsKey
      .split(",")
      .map((id) => Number(id))
      .filter((id) => Number.isFinite(id));

    Promise.all(
      ids.map(async (id) => {
        try {
          const response = await fetch(`/api/shop/${id}/reviews`);
          if (!response.ok) return [id, null] as const;
          return [id, (await response.json()) as TableReviewInsights] as const;
        } catch {
          return [id, null] as const;
        }
      }),
    ).then((entries) => {
      if (canceled) return;
      setInsightsByShop(Object.fromEntries(entries));
    });

    return () => {
      canceled = true;
    };
  }, [shopIdsKey]);

  if (shops.length < 2) return null;
  return (
    <section className="overflow-hidden rounded-2xl border border-black/10 bg-white/80 shadow-sm">
      <div className="border-b border-black/10 px-4 py-3">
        <h3 className="text-sm font-black text-zinc-900">快速比較</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-[980px] table-fixed text-left text-sm">
          <thead className="bg-zinc-50 text-xs font-black text-zinc-500">
            <tr>
              <th className="w-[22%] px-4 py-3">店名</th>
              <th className="w-[34%] px-4 py-3">特色亮點</th>
              <th className="w-[22%] px-4 py-3">適合情境</th>
              <th className="w-[22%] px-4 py-3">是否可線上訂位</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-black/5">
            {shops.map((shop) => {
              const insights = insightsByShop[shop.shop_id];
              const isThin = !hasRichComparisonData(shop, insights);
              return (
                <tr key={shop.shop_id} className="align-top">
                  <td className="px-4 py-3">
                    <Link href={`/shops/${shop.shop_id}`} className="font-bold text-zinc-900 hover:text-emerald-800">
                      {shop.name}
                    </Link>
                    {formatComparisonMeta(shop) ? (
                      <div className="mt-1 text-xs leading-5 text-zinc-500">{formatComparisonMeta(shop)}</div>
                    ) : null}
                  </td>
                  <td className={`px-4 py-3 leading-6 ${isThin ? "text-amber-800" : "text-zinc-700"}`}>
                    {formatFeatureHighlight(shop, insights)}
                  </td>
                  <td className="px-4 py-3 leading-6 text-zinc-700">{formatBestFor(shop, insights)}</td>
                  <td className="px-4 py-3 leading-6 text-zinc-700">{formatOnlineBookingStatus(shop, insights)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function AiProgressPanel({ message }: { message: Msg }) {
  if (message.role !== "ai") return null;
  const hasSteps = (message.toolSteps?.length ?? 0) > 0;
  const shouldShow = !message.done || hasSteps;
  if (!shouldShow) return null;

  return (
    <div className="mb-2 max-w-xl rounded-2xl border border-black/10 bg-white/75 px-3 py-2.5 shadow-sm">
      <div className="flex items-center gap-2 text-xs font-bold text-zinc-600">
        {message.done ? (
          <CheckCircle2 className="h-4 w-4 text-emerald-700" />
        ) : (
          <Loader2 className="h-4 w-4 animate-spin text-[#9a7b31]" />
        )}
        <span>{message.statusLabel ?? "正在處理"}</span>
      </div>

      {hasSteps ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {message.toolSteps?.map((step) => (
            <span
              key={step.name}
              className={`inline-flex h-7 items-center gap-1 rounded-full border px-2.5 text-[11px] font-bold ${
                step.status === "done"
                  ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                  : "border-amber-200 bg-amber-50 text-amber-900"
              }`}
            >
              {step.status === "done" ? (
                <CheckCircle2 className="h-3.5 w-3.5" />
              ) : (
                <CircleDashed className="h-3.5 w-3.5 animate-spin" />
              )}
              {step.label}
            </span>
          ))}
        </div>
      ) : !message.done ? (
        <div className="mt-2 flex items-center gap-1.5 text-[11px] text-zinc-400">
          <Search className="h-3.5 w-3.5" />
          <span>需求、地點、料理與訂位條件會依序確認</span>
        </div>
      ) : null}
    </div>
  );
}

const DEMO_PAYMENT_METHODS = [
  {
    id: "card",
    label: "信用卡 Demo",
    description: "聊天室快速確認，完整 TapPay flow 請到我的訂位",
  },
  {
    id: "line-pay",
    label: "LINE Pay",
    description: "錢包 demo flow",
  },
  {
    id: "apple-pay",
    label: "Apple Pay",
    description: "錢包 demo flow",
  },
  {
    id: "jko-pay",
    label: "街口支付",
    description: "錢包 demo flow",
  },
] as const;

function formatHoldCountdown(holdExpiresAt: string | null | undefined, nowMs: number) {
  if (!holdExpiresAt) return null;
  const remainingMs = new Date(holdExpiresAt).getTime() - nowMs;
  if (remainingMs <= 0) return "已逾期";
  const totalSeconds = Math.ceil(remainingMs / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function AgentBookingConfirmationCard({ transaction }: { transaction: AgentTransaction }) {
  const [current, setCurrent] = useState(transaction);
  const [paying, setPaying] = useState(false);
  const [payError, setPayError] = useState<string | null>(null);
  const [nowMs, setNowMs] = useState(() => Date.now());
  const [selectedPaymentMethod, setSelectedPaymentMethod] =
    useState<(typeof DEMO_PAYMENT_METHODS)[number]["id"]>("card");
  const [cardNumber, setCardNumber] = useState("4242 4242 4242 4242");
  const [cardExpiry, setCardExpiry] = useState("12/30");
  const [cardCcv, setCardCcv] = useState("123");
  const paid = current.status === "PAID";
  const confirmed = current.status === "CONFIRMED" || paid;
  const shopLabel = current.shop_name ?? `店家 ID ${current.shop_id ?? "-"}`;
  const selectedPayment = DEMO_PAYMENT_METHODS.find((method) => method.id === selectedPaymentMethod);
  const holdCountdown = formatHoldCountdown(current.hold_expires_at, nowMs);
  const holdExpired = current.status === "PENDING_PAYMENT" && holdCountdown === "已逾期";

  useEffect(() => {
    if (current.status !== "PENDING_PAYMENT" || !current.hold_expires_at) return;
    const timer = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [current.hold_expires_at, current.status]);

  async function handleDemoPay() {
    if (!current.booking_code || paying) return;
    if (holdExpired) {
      setPayError("此保留已逾期，請重新建立訂位");
      return;
    }
    setPaying(true);
    setPayError(null);
    if (selectedPaymentMethod === "card") {
      const normalizedCard = cardNumber.replace(/\s/g, "");
      if (!/^\d{16}$/.test(normalizedCard) || !/^\d{2}\/\d{2}$/.test(cardExpiry) || !/^\d{3,4}$/.test(cardCcv)) {
        setPayError("請填入測試卡號、有效期限與 CCV。");
        setPaying(false);
        return;
      }
    }
    try {
      const response = await javaApi.payBookingWithTestCard(current.booking_code);
      if (!response.success) throw new Error(response.errorMsg ?? "付款失敗");
      setCurrent({
        ...current,
        success: true,
        status: "PAID",
        rec_trade_id: response.data.rec_trade_id,
        payment_amount: response.data.amount,
        payment_note: `${selectedPayment?.label ?? "Demo"} 付款完成：${response.data.note ?? "非真實扣款"}`,
      });
    } catch (err) {
      setPayError(err instanceof Error ? err.message : "付款失敗，請再試一次");
    } finally {
      setPaying(false);
    }
  }

  if (current.status === "FAILED") {
    return (
      <Card className="mt-3 w-full overflow-hidden border-rose-200 bg-gradient-to-br from-rose-50 to-stone-50 shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base text-rose-950">
            <AlertTriangle className="h-5 w-5 text-rose-600" />
            訂位未建立
            <Badge variant="secondary" className="ml-auto bg-white/80 text-rose-700">
              FAILED
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div className="rounded-xl border border-rose-100 bg-white/75 p-4 text-rose-950">
            <p className="font-semibold">{current.error ?? "此時段目前無法建立訂位。"}</p>
            <p className="mt-2 text-xs leading-5 text-rose-800/80">
              尚未建立訂位、未產生訂位編號，也不會進入付款流程。
            </p>
          </div>
          <div className="rounded-xl border border-stone-200 bg-white/75 p-3 text-xs leading-5 text-stone-700">
            建議改查其他時段、降低人數，或回到店家後台調整此時段 capacity 後再試。
          </div>
        </CardContent>
      </Card>
    );
  }

  if (current.status === "PAYMENT_FAILED") {
    return (
      <Card className="mt-3 w-full overflow-hidden border-amber-200 bg-gradient-to-br from-amber-50 to-stone-50 shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base text-amber-950">
            <CreditCard className="h-5 w-5 text-amber-700" />
            訂金付款未完成
            <Badge variant="secondary" className="ml-auto bg-white/80 text-amber-800">
              PAYMENT_FAILED
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          <div className="grid gap-3 rounded-xl border border-amber-100 bg-white/75 p-4 md:grid-cols-2">
            <div>
              <p className="text-xs text-muted-foreground">店家</p>
              <p className="font-semibold text-foreground">{shopLabel}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">訂位編號</p>
              <p className="font-mono font-semibold text-foreground">{current.booking_code ?? "-"}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">人數</p>
              <p className="font-medium">{current.people ?? "-"} 人</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">時間</p>
              <p className="font-medium">
                {current.date ?? "-"} {current.time ?? ""}
              </p>
            </div>
          </div>
          <div className="rounded-xl border border-amber-200 bg-amber-50/80 p-4 text-xs text-amber-900">
            <p className="font-semibold">錯誤：{current.error ?? "付款流程未完成"}</p>
            <p className="mt-2">此訂位需要訂金，付款成功前不應視為完成。</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="mt-3 w-full overflow-hidden border-emerald-200 bg-gradient-to-br from-emerald-50 to-stone-50 shadow-sm">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base text-emerald-950">
          <CalendarCheck className="h-5 w-5 text-emerald-700" />
          {confirmed ? "訂位確認" : "訂位待付款"}
          <Badge variant="secondary" className="ml-auto bg-white/70 text-emerald-800">
            {current.status}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div className="grid gap-3 rounded-xl border border-emerald-100 bg-white/70 p-4 md:grid-cols-2">
          <div>
            <p className="text-xs text-muted-foreground">店家</p>
            <p className="font-semibold text-foreground">{shopLabel}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">訂位編號</p>
            <p className="font-mono font-semibold text-foreground">{current.booking_code ?? "-"}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">人數</p>
            <p className="font-medium">{current.people ?? "-"} 人</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">時間</p>
            <p className="font-medium">
              {current.date ?? "-"} {current.time ?? ""}
            </p>
          </div>
        </div>

        {current.needs_deposit ? (
          <div className="rounded-xl border border-amber-200 bg-amber-50/80 p-4">
            <div className="mb-2 flex items-center gap-2 font-medium text-amber-950">
              <CreditCard className="h-4 w-4" />
              訂金付款
            </div>
            <div className="grid gap-2 text-xs text-amber-900 md:grid-cols-3">
              <p>金額：NT$ {current.deposit_total ?? current.payment_amount ?? "-"}</p>
              <p>狀態：{paid ? "已付款" : holdExpired ? "已逾期" : "待付款"}</p>
              <p className="truncate">交易編號：{current.rec_trade_id ?? "-"}</p>
            </div>
            {!paid && holdCountdown ? (
              <p className={`mt-2 text-[11px] font-semibold ${holdExpired ? "text-red-700" : "text-amber-800"}`}>
                座位保留倒數：{holdCountdown}。完成付款後訂位才成立。
              </p>
            ) : null}
            {current.payment_note ? (
              <p className="mt-2 text-[11px] text-amber-800">{current.payment_note}</p>
            ) : null}
            {!paid && current.booking_code && !holdExpired ? (
              <div className="mt-4 space-y-3 rounded-xl border border-amber-200 bg-white/70 p-3">
                <div>
                  <p className="text-sm font-semibold text-amber-950">選擇付款方式</p>
                  <p className="mt-1 text-[11px] leading-5 text-amber-800">
                    本地 demo 不會扣款；正式上線應在這一步接 TapPay client confirmation 或第三方錢包授權。
                  </p>
                </div>
                <div className="grid gap-2 md:grid-cols-4">
                  {DEMO_PAYMENT_METHODS.map((method) => (
                    <button
                      key={method.id}
                      type="button"
                      onClick={() => setSelectedPaymentMethod(method.id)}
                      className={`rounded-xl border p-3 text-left transition ${
                        selectedPaymentMethod === method.id
                          ? "border-amber-600 bg-amber-100 text-amber-950"
                          : "border-stone-200 bg-white text-stone-700 hover:border-amber-300"
                      }`}
                    >
                      <span className="block text-sm font-bold">{method.label}</span>
                      <span className="mt-1 block text-[11px] leading-4 text-muted-foreground">
                        {method.description}
                      </span>
                    </button>
                  ))}
                </div>
                {selectedPaymentMethod === "card" ? (
                  <div className="rounded-xl border border-stone-200 bg-stone-50/80 p-3">
                    <div className="mb-2 flex items-center justify-between gap-3">
                      <p className="text-xs font-semibold text-stone-800">Demo 信用卡確認</p>
                      <span className="rounded-full bg-white px-2 py-0.5 text-[10px] font-semibold text-stone-500">
                        測試卡
                      </span>
                    </div>
                    <div className="grid gap-2 md:grid-cols-[1.4fr_0.7fr_0.5fr]">
                      <label className="text-[11px] font-medium text-stone-600">
                        卡號
                        <input
                          value={cardNumber}
                          onChange={(event) => setCardNumber(event.target.value)}
                          inputMode="numeric"
                          className="mt-1 h-9 w-full rounded-lg border border-stone-200 bg-white px-3 text-sm text-stone-950"
                          placeholder="4242 4242 4242 4242"
                        />
                      </label>
                      <label className="text-[11px] font-medium text-stone-600">
                        有效期限
                        <input
                          value={cardExpiry}
                          onChange={(event) => setCardExpiry(event.target.value)}
                          className="mt-1 h-9 w-full rounded-lg border border-stone-200 bg-white px-3 text-sm text-stone-950"
                          placeholder="MM/YY"
                        />
                      </label>
                      <label className="text-[11px] font-medium text-stone-600">
                        CCV
                        <input
                          value={cardCcv}
                          onChange={(event) => setCardCcv(event.target.value)}
                          inputMode="numeric"
                          className="mt-1 h-9 w-full rounded-lg border border-stone-200 bg-white px-3 text-sm text-stone-950"
                          placeholder="123"
                        />
                      </label>
                    </div>
                    <p className="mt-2 text-[11px] leading-5 text-stone-500">
                      聊天室使用 demo confirmation，方便展示 Agent transaction；完整 TapPay iframe prime flow 已放在「我的訂位」付款頁。
                    </p>
                  </div>
                ) : null}
                <Button
                  size="sm"
                  className="w-full bg-amber-700 text-white hover:bg-amber-800"
                  disabled={paying}
                  onClick={handleDemoPay}
                >
                  {paying
                    ? "付款處理中..."
                    : `確認以${selectedPayment?.label ?? "Demo"}支付 NT$ ${
                        current.deposit_total ?? current.payment_amount ?? "-"
                      }`}
                </Button>
                {payError ? <p className="text-xs font-medium text-rose-700">{payError}</p> : null}
              </div>
            ) : !paid && holdExpired ? (
              <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-xs font-semibold text-red-700">
                此保留已逾期，座位容量會釋放；請重新建立訂位。
              </div>
            ) : null}
          </div>
        ) : (
          <div className="rounded-xl border border-emerald-100 bg-white/70 p-3 text-xs text-emerald-900">
            此店家免訂金，已直接確認訂位。
          </div>
        )}

        {current.shop_id ? (
          <Link href={`/shops/${current.shop_id}`}>
            <Button size="sm" className="w-full bg-emerald-700 hover:bg-emerald-800">
              查看店家詳情
            </Button>
          </Link>
        ) : null}
      </CardContent>
    </Card>
  );
}

/** 產生或讀取 localStorage session id */
function getOrCreateSessionId(): string {
  if (typeof window === "undefined") return "";
  let id = localStorage.getItem("bytebites_chat_session");
  if (!id) {
    id =
      "sess-" +
      Math.random().toString(36).slice(2, 12) +
      Date.now().toString(36);
    localStorage.setItem("bytebites_chat_session", id);
  }
  return id;
}

export default function AiPage() {
  const { isLoggedIn, login, mounted } = useAuth();
  const [query, setQuery] = useState(() => {
    if (typeof window === "undefined") return "";
    return new URLSearchParams(window.location.search).get("q") ?? "";
  });
  const [loading, setLoading] = useState(false);

  const [messages, setMessages] = useState<Msg[]>([]);
  const [sessionId, setSessionId] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setSessionId(getOrCreateSessionId());
  }, []);

  // scroll container to bottom whenever messages or loading state changes
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, loading]);

  async function sendAgentMessage(q: string) {
    if (!q.trim()) return;
    const userMsg = q.trim();
    if (mounted && !isLoggedIn) {
      setMessages((prev) => [
        ...prev,
        { role: "user", content: userMsg },
        {
          role: "ai",
          content: "請先用 LINE 登入，再使用 ByteBites AI。這樣推薦、訂位、付款與空位通知才會同步到你的帳號。",
          done: true,
        },
      ]);
      setQuery("");
      return;
    }
    const activeSessionId = sessionId || getOrCreateSessionId();
    if (!sessionId) setSessionId(activeSessionId);
    setMessages((prev) => [
      ...prev,
      { role: "user", content: userMsg },
      { role: "ai", content: "", toolsUsed: [] },
    ]);
    setQuery("");
    setLoading(true);
    try {
      await streamAgentResponse(
        { query: userMsg, session_id: activeSessionId },
        (event) => {
          if (event.type === "agent_start") {
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              if (!last || last.role !== "ai") return prev;
              next[next.length - 1] = {
                ...last,
                statusLabel: STATUS_LABELS.agent_start,
                streamMode: "lifecycle",
              };
              return next;
            });
          } else if (event.type === "turn_start") {
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              if (!last || last.role !== "ai") return prev;
              next[next.length - 1] = {
                ...last,
                statusLabel: STATUS_LABELS.turn_start,
                streamMode: "lifecycle",
              };
              return next;
            });
          } else if (event.type === "tool_execution_start") {
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              if (!last || last.role !== "ai") return prev;
              next[next.length - 1] = {
                ...last,
                statusLabel: `${STATUS_LABELS.tool_execution_start}：${toolLabel(event.name)}`,
                streamMode: "lifecycle",
                toolSteps: upsertToolStep(last.toolSteps, event.name, "active"),
                toolsUsed: uniqueTools(last.toolsUsed, event.name),
              };
              return next;
            });
          } else if (event.type === "tool_execution_end") {
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              if (!last || last.role !== "ai") return prev;
              next[next.length - 1] = {
                ...last,
                statusLabel: STATUS_LABELS.tool_execution_end,
                streamMode: "lifecycle",
                toolSteps: upsertToolStep(last.toolSteps, event.name, "done"),
                toolsUsed: uniqueTools(last.toolsUsed, event.name),
              };
              return next;
            });
          } else if (event.type === "message_update") {
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              if (!last || last.role !== "ai") return prev;
              next[next.length - 1] = {
                ...last,
                content: `${last.content}${event.content}`,
                statusLabel: STATUS_LABELS.message_update,
                streamMode: "lifecycle",
              };
              return next;
            });
          } else if (event.type === "chunk") {
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              if (!last || last.role !== "ai") return prev;
              if (last.streamMode === "lifecycle") return prev;
              next[next.length - 1] = { ...last, content: `${last.content}${event.content}` };
              return next;
            });
          } else if (event.type === "tool") {
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              if (!last || last.role !== "ai") return prev;
              if (last.streamMode === "lifecycle") return prev;
              const tools = uniqueTools(last.toolsUsed, event.name);
              next[next.length - 1] = {
                ...last,
                toolsUsed: tools,
                toolSteps: upsertToolStep(last.toolSteps, event.name, "done"),
              };
              return next;
            });
          } else if (event.type === "agent_end" || event.type === "done") {
            const toolResult = event.tool_result as { shops?: AgentShop[] } | undefined;
            const shops = selectRecommendedShops(
              toolResult?.shops,
              event.recommended_shop_ids,
            );
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              if (!last || last.role !== "ai") return prev;
              if (event.type === "done" && last.finalEventHandled) return prev;
              next[next.length - 1] = {
                ...last,
                content: event.answer || last.content,
                statusLabel: STATUS_LABELS.agent_end,
                toolsUsed: event.tools_used ?? last.toolsUsed,
                shops: shops ?? last.shops,
                transaction: event.transaction ?? last.transaction,
                finalEventHandled: true,
                done: true,
              };
              return next;
            });
          } else if (event.type === "agent_error" || event.type === "error") {
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              if (!last || last.role !== "ai") return prev;
              next[next.length - 1] = {
                ...last,
                content: event.message || "出錯了，再試一次",
                statusLabel: STATUS_LABELS.agent_error,
                done: true,
              };
              return next;
            });
          }
        },
      );
    } catch {
      setMessages((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (!last || last.role !== "ai") return [...prev, { role: "ai", content: "出錯了，再試一次" }];
        next[next.length - 1] = { ...last, content: "出錯了，再試一次" };
        return next;
      });
    } finally {
      setLoading(false);
    }
  }

  async function handleClearChat() {
    setMessages([]);
    const activeSessionId = sessionId || getOrCreateSessionId();
    if (!sessionId) setSessionId(activeSessionId);
    await fetch(`${AI_API}/api/ai/session/${activeSessionId}`, { method: "DELETE" }).catch(() => {});
  }

  function handleRun(q: string) {
    if (!q.trim()) return;
    void sendAgentMessage(q);
  }

  return (
    <main className="min-h-screen bg-[#f7f3ec]">
      <section className="flex min-h-screen flex-col">
        <div
          ref={scrollRef}
          className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-5 overflow-y-auto px-5 pb-6 pt-8 md:px-8"
        >
            {messages.length === 0 ? (
              <div className="mx-auto mt-16 max-w-3xl text-center md:mt-24">
                <p className="text-xs font-black tracking-[0.32em] text-[#b59a57]">
                  AI DINING CONCIERGE
                </p>
                <h1 className="mt-4 text-5xl font-black leading-tight tracking-tight md:text-7xl">
                  今晚想去哪？
                </h1>
                <p className="mx-auto mt-4 max-w-xl text-base leading-8 text-zinc-500">
                  告訴 ByteBites AI，你想吃什麼、幾個人、什麼時間。推薦、訂位、付款與空位通知都在同一個對話裡完成。
                </p>
                <div className="mt-8 flex flex-wrap justify-center gap-3">
                  {mounted && !isLoggedIn ? (
                    <button
                      type="button"
                      onClick={login}
                      className="rounded-full bg-emerald-700 px-5 py-3 text-sm font-black text-white transition hover:bg-emerald-800"
                    >
                      用 LINE 登入後開始
                    </button>
                  ) : null}
                  {PRESETS.map((preset) => (
                    <button
                      key={preset}
                      type="button"
                      onClick={() => handleRun(preset)}
                      disabled={loading || (mounted && !isLoggedIn)}
                      className="rounded-full bg-[#eee8dc] px-4 py-3 text-sm font-bold text-zinc-600 transition hover:bg-[#e5dccb] disabled:opacity-60"
                    >
                      {preset}
                    </button>
                  ))}
                </div>
                <div className="mt-8 flex flex-wrap justify-center gap-2">
                  {PRODUCT_HINTS.map((hint) => {
                    const Icon = hint.icon;
                    return (
                      <span key={hint.label} className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/70 px-3 py-1.5 text-xs font-bold text-zinc-500">
                        <Icon className="h-3.5 w-3.5" />
                        {hint.label}
                      </span>
                    );
                  })}
                </div>
              </div>
            ) : null}

            {messages.map((m, i) => (
              <div
                key={i}
                className={`flex flex-col ${m.role === "user" ? "items-end" : "items-start"}`}
              >
                <div className={m.role === "user" ? "max-w-[82%]" : "w-full"}>
                  <AiProgressPanel message={m} />
                  {m.role === "user" || m.content.trim() ? (
                    <div
                      className={`rounded-3xl px-4 py-3 text-base leading-7 ${
                        m.role === "user"
                          ? "rounded-br-sm bg-[#5a5650] text-white shadow-sm"
                          : "rounded-bl-sm bg-white/55 text-zinc-700 shadow-sm ring-1 ring-black/5"
                      }`}
                    >
                      {m.role === "user" ? (
                        <div className="whitespace-pre-wrap">{m.content}</div>
                      ) : (
                        <MarkdownMessage content={m.content} />
                      )}
                    </div>
                  ) : null}
                  {m.toolsUsed && m.toolsUsed.length > 0 ? (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {m.toolsUsed.map((tool) => (
                        <Badge key={tool} variant="secondary" className="rounded-full text-[10px]">
                          {toolLabel(tool)}
                        </Badge>
                      ))}
                    </div>
                  ) : null}
                </div>
                {m.shops && m.shops.length > 0 ? (
                  <div className="mt-3 w-full space-y-3">
                    {m.shops.map((shop, rank) => (
                      <AgentShopCard key={shop.shop_id} shop={shop} rank={rank + 1} />
                    ))}
                    <AgentShopComparisonTable shops={m.shops} />
                  </div>
                ) : null}
                {m.transaction ? (
                  <AgentBookingConfirmationCard transaction={m.transaction} />
                ) : null}
              </div>
            ))}
        </div>

        <div className="sticky bottom-0 z-40 bg-gradient-to-t from-[#f7f3ec] via-[#f7f3ec] to-transparent px-4 pb-4 pt-10">
          <div className="mx-auto max-w-5xl">
            <div className="flex items-center gap-2 rounded-full bg-white px-4 py-3 shadow-2xl shadow-black/15 ring-1 ring-black/5">
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="找餐廳 問 ByteBites AI"
                onKeyDown={(event) => event.key === "Enter" && !loading && handleRun(query)}
                disabled={loading || (mounted && !isLoggedIn)}
                className="h-11 flex-1 border-0 bg-transparent px-2 text-base shadow-none focus-visible:ring-0"
              />
              <Button
                onClick={() => handleRun(query)}
                disabled={loading || !query.trim() || (mounted && !isLoggedIn)}
                className="h-11 rounded-full bg-[#171512] px-5 font-black text-white hover:bg-black"
              >
                {loading ? "..." : "送出"}
              </Button>
              <button
                type="button"
                onClick={handleClearChat}
                className="hidden rounded-full p-2 text-zinc-400 transition hover:bg-black/5 hover:text-zinc-700 sm:inline-flex"
                aria-label="清空對話"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
            <p className="mt-2 text-center text-[11px] text-zinc-400">
              AI 建議僅供參考，請以店家公告為主
              {sessionId ? ` · Session ${sessionId.slice(0, 16)}` : ""}
            </p>
          </div>
        </div>
      </section>
    </main>
  );
}
