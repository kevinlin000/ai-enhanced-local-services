"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { CheckCircle2, CircleDashed, Loader2, Send, Sparkles, X } from "lucide-react";
import { streamAgentResponse, type AgentTransaction } from "@/lib/agentStream";
import { MarkdownMessage } from "@/components/MarkdownMessage";
import { useAuth } from "@/lib/auth";
import type { AgentShop } from "@/lib/agentTypes";
import {
  agentToolLabel,
  type AgentChatMessage,
  updateLastAiMessage,
} from "@/lib/agentMessages";

type Msg = AgentChatMessage;

const TOOL_LABELS: Record<string, string> = {
  search_shops_by_mrt: "搜尋捷運附近",
  semantic_shop_search: "比對餐廳資料",
  create_hot_seat_order: "建立 Hot Seat",
  create_booking: "建立訂位",
  pay_booking_with_test_card: "確認付款",
  cancel_booking: "取消訂位",
};

function toolLabel(name: string): string {
  return agentToolLabel(name, TOOL_LABELS);
}

function formatShopMeta(shop: AgentShop): string {
  return [
    shop.district,
    shop.mrt_station ? `捷運${shop.mrt_station}` : null,
    shop.price_per_person ?? (shop.avg_price != null ? `NT$ ${shop.avg_price}` : null),
  ]
    .filter(Boolean)
    .join(" · ");
}

function CompactShopPreview({ shop, rank }: { shop: AgentShop; rank: number }) {
  const summary = (shop.ai_summary ?? "").replace(/\s+/g, " ").trim();
  const dishes = (shop.signature_dishes ?? []).filter(Boolean).slice(0, 2).join("、");
  return (
    <Link
      href={`/shops/${shop.shop_id}`}
      className="block rounded-xl border border-foreground/10 bg-background/80 px-3 py-2.5 text-left transition hover:border-primary/40"
    >
      <div className="flex items-center gap-2">
        <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-white">
          {rank}
        </span>
        <span className="min-w-0 flex-1 truncate text-xs font-bold text-foreground">{shop.name}</span>
      </div>
      {formatShopMeta(shop) ? (
        <div className="mt-1 truncate text-[11px] text-muted-foreground">{formatShopMeta(shop)}</div>
      ) : null}
      {dishes || summary ? (
        <div className="mt-1 line-clamp-2 text-[11px] leading-5 text-muted-foreground">
          {dishes ? `招牌：${dishes}` : summary}
        </div>
      ) : null}
    </Link>
  );
}

function CompactTransactionStatus({ transaction }: { transaction: AgentTransaction }) {
  const shopLabel = transaction.shop_name ?? `店家 ID ${transaction.shop_id ?? "-"}`;
  const statusLabel: Record<AgentTransaction["status"], string> = {
    CONFIRMED: "訂位完成",
    PAID: "已付款",
    PENDING_PAYMENT: "待付訂金",
    PAYMENT_FAILED: "付款未完成",
    FAILED: "訂位失敗",
    EXPIRED: "保留逾期",
    CANCELED: "已取消",
  };
  return (
    <div className="mt-3 rounded-xl border border-foreground/10 bg-background/80 px-3 py-2.5 text-xs leading-5">
      <div className="flex items-center justify-between gap-2">
        <span className="font-bold text-foreground">{statusLabel[transaction.status]}</span>
        {transaction.booking_code ? (
          <span className="font-mono text-[10px] text-muted-foreground">{transaction.booking_code}</span>
        ) : null}
      </div>
      <div className="mt-1 text-muted-foreground">
        {shopLabel} · {transaction.date ?? "-"} {transaction.time ?? ""}
      </div>
      {transaction.status === "PENDING_PAYMENT" ? (
        <Link href="/bookings" className="mt-2 inline-flex rounded-full bg-primary px-3 py-1 text-[11px] font-bold text-white">
          前往付款
        </Link>
      ) : null}
    </div>
  );
}

export function AiConcierge() {
  const pathname = usePathname();
  const { isLoggedIn, isAuthLoading, login, mounted } = useAuth();
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<Msg[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  // stable session id — shared with /ai page via localStorage
  const [sessionId] = useState(() => {
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
  });

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, loading]);

  const handleSend = async () => {
    const msg = input.trim();
    if (!msg || loading) return;
    if (mounted && isAuthLoading) return;
    if (mounted && !isLoggedIn) {
      setMessages((prev) => [
        ...prev,
        { role: "user", content: msg },
        { role: "ai", content: "請先用 LINE 登入，再使用 ByteBites AI。這樣推薦、訂位、付款與通知才會同步到你的帳號。", done: true },
      ]);
      setInput("");
      return;
    }
    setInput("");
    setMessages((prev) => [
      ...prev,
      { role: "user", content: msg },
      { role: "ai", content: "", toolsUsed: [], query: msg },
    ]);
    setLoading(true);
    try {
      await streamAgentResponse(
        { query: msg, session_id: sessionId },
        (event) => {
          setMessages((prev) =>
            updateLastAiMessage(prev, event, {
              toolLabels: TOOL_LABELS,
              statusLabels: {
                turn_start: "正在理解需求",
                tool_execution_start: "處理中",
                tool_execution_end: "資料已取得",
              },
              errorMessage: "錯誤、再試一次",
            }),
          );
        },
      );
    } catch {
      setMessages((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (!last || last.role !== "ai") {
          return [...prev, { role: "ai", content: "錯誤、再試一次", done: true, statusLabel: "處理失敗" }];
        }
        next[next.length - 1] = { ...last, content: "錯誤、再試一次", done: true, statusLabel: "處理失敗" };
        return next;
      });
    } finally {
      setLoading(false);
    }
  };

  const handleClear = async () => {
    setMessages([]);
    await fetch(`/api/ai/session/${sessionId}`, { method: "DELETE" }).catch(
      () => {}
    );
  };

  return (
    <>
      {/* Mobile shortcut only. Desktop already has the persistent AI entry in the app sidebar. */}
      {!open && pathname !== "/ai" && (
        <button
          onClick={() => setOpen(true)}
          className="fixed right-6 bottom-6 z-40 flex h-14 w-14 items-center justify-center rounded-full bg-primary text-white shadow-lg transition hover:scale-105 md:hidden"
          aria-label="AI Concierge"
        >
          <Sparkles className="h-6 w-6" />
        </button>
      )}

      {/* Right sidebar */}
      {open && (
        <div className="fixed inset-y-0 right-0 z-50 flex w-full flex-col border-l bg-background shadow-2xl md:w-[420px]">
          {/* Header */}
          <div className="flex shrink-0 items-center justify-between border-b px-5 py-4">
            <div className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-primary" />
              <span className="font-semibold">AI Concierge</span>
              <span className="rounded bg-muted px-2 py-0.5 font-mono text-xs">
                Agent · Gemini
              </span>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={handleClear}
                className="text-xs text-muted-foreground hover:text-foreground"
              >
                清空
              </button>
              <button
                onClick={() => setOpen(false)}
                className="text-muted-foreground hover:text-foreground"
                aria-label="關閉"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
          </div>

          {/* Messages — flex-1 + min-h-0 critical for scroll in flex column */}
          <div
            ref={scrollRef}
            className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4"
          >
            {messages.length === 0 && (
              <div className="py-8 text-center text-sm text-muted-foreground">
                <Sparkles className="mx-auto mb-2 h-8 w-8 text-primary/50" />
                {mounted && !isAuthLoading && !isLoggedIn ? (
                  <>
                    <p className="font-semibold text-foreground">請先用 LINE 登入</p>
                    <p className="mt-2 leading-6">AI 對話會連動訂位、付款與通知。</p>
                    <button
                      type="button"
                      onClick={login}
                      className="mt-4 rounded-full bg-primary px-4 py-2 text-xs font-bold text-white"
                    >
                      用 LINE 登入
                    </button>
                  </>
                ) : (
                  <>
                    <p>試試問我：</p>
                    <p className="mt-2">「信義區想吃火鍋」</p>
                    <p>「適合約會的鐵板燒」</p>
                    <p>「幫我訂明天 7 點 2 人」</p>
                  </>
                )}
              </div>
            )}

            {messages.map((m, i) => (
              <div
                key={i}
                className={
                  m.role === "user" ? "flex justify-end" : "flex justify-start"
                }
              >
                <div className="max-w-[85%]">
                  {m.role === "ai" && (!m.done || (m.toolSteps?.length ?? 0) > 0) ? (
                    <div className="mb-1.5 rounded-xl border bg-background px-3 py-2 shadow-sm">
                      <div className="flex items-center gap-2 text-[11px] font-semibold text-muted-foreground">
                        {m.done ? (
                          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-700" />
                        ) : (
                          <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
                        )}
                        {m.statusLabel ?? "正在處理"}
                      </div>
                      {(m.toolSteps?.length ?? 0) > 0 ? (
                        <div className="mt-2 flex flex-wrap gap-1">
                          {m.toolSteps?.map((step) => (
                            <span
                              key={step.name}
                              className={`inline-flex h-6 items-center gap-1 rounded-full px-2 text-[10px] font-semibold ${
                                step.status === "done"
                                  ? "bg-emerald-50 text-emerald-800"
                                  : "bg-amber-50 text-amber-900"
                              }`}
                            >
                              {step.status === "done" ? (
                                <CheckCircle2 className="h-3 w-3" />
                              ) : (
                                <CircleDashed className="h-3 w-3 animate-spin" />
                              )}
                              {step.label}
                            </span>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                  <div
                    className={`rounded-2xl px-4 py-2.5 text-sm ${
                      m.role === "user"
                        ? "rounded-br-sm bg-primary text-white"
                        : "rounded-bl-sm bg-muted"
                    }`}
                  >
                    {m.role === "ai" ? (
                      <MarkdownMessage content={m.content} compact />
                    ) : (
                      <span>{m.content}</span>
                    )}

                    {m.hits && m.hits.length > 0 && (
                      <div className="mt-2 space-y-1 border-t border-foreground/10 pt-2">
                        {m.hits.slice(0, 3).map((h) => (
                          <Link
                            key={h.shop_id}
                            href={`/shops/${h.shop_id}`}
                            className="block text-xs text-primary hover:underline"
                          >
                            → {h.name} · {h.district}
                          </Link>
                        ))}
                      </div>
                    )}

                    {m.role === "ai" && m.done && (m.shops?.length ?? 0) > 0 && m.query && (
                      <div className="mt-3 space-y-2 border-t border-foreground/10 pt-2.5">
                        {m.scopeNote ? (
                          <div className="rounded-xl bg-amber-50 px-3 py-2 text-left text-[11px] leading-5 text-amber-950">
                            {m.scopeNote}
                          </div>
                        ) : null}
                        {m.shops?.slice(0, 3).map((shop, rank) => (
                          <CompactShopPreview key={shop.shop_id} shop={shop} rank={rank + 1} />
                        ))}
                        <Link
                          href={`/ai?q=${encodeURIComponent(m.query)}`}
                          onClick={() => setOpen(false)}
                          className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary transition hover:bg-primary/20"
                        >
                          查看完整卡片與比較表 →
                        </Link>
                      </div>
                    )}

                    {m.role === "ai" && m.done && m.transaction ? (
                      <CompactTransactionStatus transaction={m.transaction} />
                    ) : null}
                  </div>

                  {m.toolsUsed && m.toolsUsed.length > 0 && (
                    <div className="mt-1 flex flex-wrap gap-1">
                      {m.toolsUsed.map((t, idx) => (
                        <span
                          key={idx}
                          className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground"
                        >
                          {toolLabel(t)}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {loading && messages[messages.length - 1]?.role !== "ai" && (
              <div className="flex justify-start">
                <div className="rounded-2xl rounded-bl-sm bg-muted px-4 py-2.5 text-sm">
                  <span className="inline-flex gap-1">
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-foreground/40" />
                    <span
                      className="h-1.5 w-1.5 animate-bounce rounded-full bg-foreground/40"
                      style={{ animationDelay: "0.2s" }}
                    />
                    <span
                      className="h-1.5 w-1.5 animate-bounce rounded-full bg-foreground/40"
                      style={{ animationDelay: "0.4s" }}
                    />
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* Input */}
          <div className="shrink-0 border-t px-4 py-3">
            <div className="flex items-center gap-2">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                placeholder="輸入你想吃什麼..."
                className="flex-1 rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                disabled={loading || isAuthLoading || (mounted && !isLoggedIn)}
              />
              <button
                onClick={handleSend}
                disabled={loading || isAuthLoading || !input.trim() || (mounted && !isLoggedIn)}
                aria-label="送出"
                className="rounded-lg bg-primary p-2 text-white hover:bg-primary/90 disabled:opacity-50"
              >
                <Send className="h-4 w-4" />
              </button>
            </div>
            <p className="mt-2 text-center text-[10px] text-muted-foreground">
              Powered by Gemini · Redis session · multi-turn
            </p>
          </div>
        </div>
      )}
    </>
  );
}
