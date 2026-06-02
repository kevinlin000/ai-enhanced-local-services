"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { AlertTriangle, Bell, Bot, CalendarCheck, CreditCard, Heart, Sparkles, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { javaApi } from "@/lib/api";
import { streamAgentResponse, type AgentTransaction } from "@/lib/agentStream";
import { AgentShopCard, type AgentShop } from "@/components/AgentShopCard";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const AI_API = "";

interface Msg {
  role: "user" | "ai";
  content: string;
  toolsUsed?: string[];
  shops?: AgentShop[];
  transaction?: AgentTransaction;
}

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

function shopId(shop: AgentShop): number {
  return shop.shop_id;
}

function selectRecommendedShops(
  shops: AgentShop[] | undefined,
  recommendedShopIds: number[] | undefined,
): AgentShop[] | undefined {
  if (!shops || !recommendedShopIds?.length) return undefined;
  const byId = new Map(shops.map((shop) => [shopId(shop), shop]));
  return recommendedShopIds
    .map((id) => byId.get(Number(id)))
    .filter((shop): shop is AgentShop => Boolean(shop));
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
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);

  const [messages, setMessages] = useState<Msg[]>([]);
  const [sessionId] = useState<string>(getOrCreateSessionId);
  const scrollRef = useRef<HTMLDivElement>(null);

  // scroll container to bottom whenever messages or loading state changes
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, loading]);

  // Prefill query from ?q= URL param (e.g. arriving from AiConcierge CTA)
  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const q = params.get("q");
    if (!q) return;
    setQuery(q);
  }, []);

  async function sendAgentMessage(q: string) {
    if (!q.trim()) return;
    const userMsg = q.trim();
    setMessages((prev) => [
      ...prev,
      { role: "user", content: userMsg },
      { role: "ai", content: "", toolsUsed: [] },
    ]);
    setQuery("");
    setLoading(true);
    try {
      await streamAgentResponse(
        { query: userMsg, session_id: sessionId },
        (event) => {
          if (event.type === "chunk") {
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              if (!last || last.role !== "ai") return prev;
              next[next.length - 1] = { ...last, content: `${last.content}${event.content}` };
              return next;
            });
          } else if (event.type === "tool") {
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              if (!last || last.role !== "ai") return prev;
              const tools = [...new Set([...(last.toolsUsed ?? []), event.name])];
              next[next.length - 1] = { ...last, toolsUsed: tools };
              return next;
            });
          } else if (event.type === "done") {
            const toolResult = event.tool_result as { shops?: AgentShop[] } | undefined;
            const shops = selectRecommendedShops(
              toolResult?.shops,
              event.recommended_shop_ids,
            );
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              if (!last || last.role !== "ai") return prev;
              next[next.length - 1] = {
                ...last,
                content: event.answer || last.content,
                toolsUsed: event.tools_used ?? last.toolsUsed,
                shops: shops ?? last.shops,
                transaction: event.transaction ?? last.transaction,
              };
              return next;
            });
          } else if (event.type === "error") {
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              if (!last || last.role !== "ai") return prev;
              next[next.length - 1] = { ...last, content: event.message || "出錯了，再試一次" };
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
    await fetch(`${AI_API}/api/ai/session/${sessionId}`, { method: "DELETE" }).catch(() => {});
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
                  {PRESETS.map((preset) => (
                    <button
                      key={preset}
                      type="button"
                      onClick={() => handleRun(preset)}
                      disabled={loading}
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
                  <div
                    className={`rounded-3xl px-4 py-3 text-base leading-7 ${
                      m.role === "user"
                        ? "rounded-br-sm bg-[#5a5650] text-white shadow-sm"
                        : "rounded-bl-sm text-zinc-700"
                    }`}
                  >
                    {m.role === "user" ? (
                      <div className="whitespace-pre-wrap">{m.content}</div>
                    ) : (
                      <div className="prose prose-zinc max-w-none">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {m.content}
                        </ReactMarkdown>
                      </div>
                    )}
                  </div>
                  {m.toolsUsed && m.toolsUsed.length > 0 ? (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {m.toolsUsed.map((tool) => (
                        <Badge key={tool} variant="secondary" className="rounded-full text-[10px]">
                          {tool}
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
                  </div>
                ) : null}
                {m.transaction ? (
                  <AgentBookingConfirmationCard transaction={m.transaction} />
                ) : null}
              </div>
            ))}

            {loading ? (
              <div className="flex justify-start">
                <div className="rounded-3xl rounded-bl-sm bg-white px-4 py-3 text-sm text-zinc-500 shadow-sm">
                  正在查詢可訂狀態與推薦理由...
                </div>
              </div>
            ) : null}
        </div>

        <div className="sticky bottom-0 z-40 bg-gradient-to-t from-[#f7f3ec] via-[#f7f3ec] to-transparent px-4 pb-4 pt-10">
          <div className="mx-auto max-w-5xl">
            <div className="flex items-center gap-2 rounded-full bg-white px-4 py-3 shadow-2xl shadow-black/15 ring-1 ring-black/5">
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="找餐廳 問 ByteBites AI"
                onKeyDown={(event) => event.key === "Enter" && !loading && handleRun(query)}
                disabled={loading}
                className="h-11 flex-1 border-0 bg-transparent px-2 text-base shadow-none focus-visible:ring-0"
              />
              <Button
                onClick={() => handleRun(query)}
                disabled={loading || !query.trim()}
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
              AI 建議僅供參考，請以店家公告為主 · Session {sessionId.slice(0, 16)}
            </p>
          </div>
        </div>
      </section>
    </main>
  );
}
