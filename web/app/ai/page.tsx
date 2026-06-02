"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Bot, CalendarCheck, CreditCard, MapPin, Search, Sparkles, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { aiApi, type SearchHit } from "@/lib/api";
import { streamAgentResponse, type AgentTransaction } from "@/lib/agentStream";
import { AgentShopCard, type AgentShop } from "@/components/AgentShopCard";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const AI_API = "";

type Mode = "search" | "recommend" | "agent";

interface Msg {
  role: "user" | "ai";
  content: string;
  hits?: SearchHit[];
  toolsUsed?: string[];
  shops?: AgentShop[];
  transaction?: AgentTransaction;
}

const PRESETS: Record<Mode, string[]> = {
  search: ["中山站附近高級火鍋", "信義區熱門日式料理", "有 Hot Seat 的熱門餐廳"],
  recommend: ["適合約會的高級餐廳", "商務請客台菜", "信義區難訂的餐廳"],
  agent: ["信義區想吃火鍋", "中山站附近推薦", "幫我訂明天晚上 7 點 2 人"],
};

const CATEGORY_LABELS: Record<string, string> = {
  hotpot: "火鍋",
  yakiniku: "日式燒肉",
  izakaya: "居酒屋",
  japanese: "日式料理",
  omakase: "無菜單料理",
  steakhouse: "牛排館",
  european: "義法 / 西式",
  chinese: "中式料理",
  korean: "韓式料理",
  brunch: "美式料理",
  "fine-dining": "高級餐廳",
  "cafe-premium": "甜點 / 咖啡",
};

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

function AgentBookingConfirmationCard({ transaction }: { transaction: AgentTransaction }) {
  const paid = transaction.status === "PAID";
  const confirmed = transaction.status === "CONFIRMED" || paid;
  const title = confirmed ? "訂位確認" : "訂位處理狀態";
  const shopLabel = transaction.shop_name ?? `店家 ID ${transaction.shop_id ?? "-"}`;

  return (
    <Card className="mt-3 w-full overflow-hidden border-emerald-200 bg-gradient-to-br from-emerald-50 to-stone-50 shadow-sm">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base text-emerald-950">
          <CalendarCheck className="h-5 w-5 text-emerald-700" />
          {title}
          <Badge variant="secondary" className="ml-auto bg-white/70 text-emerald-800">
            {transaction.status}
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
            <p className="font-mono font-semibold text-foreground">{transaction.booking_code ?? "-"}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">人數</p>
            <p className="font-medium">{transaction.people ?? "-"} 人</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">時間</p>
            <p className="font-medium">
              {transaction.date ?? "-"} {transaction.time ?? ""}
            </p>
          </div>
        </div>

        {transaction.needs_deposit ? (
          <div className="rounded-xl border border-amber-200 bg-amber-50/80 p-4">
            <div className="mb-2 flex items-center gap-2 font-medium text-amber-950">
              <CreditCard className="h-4 w-4" />
              訂金付款
            </div>
            <div className="grid gap-2 text-xs text-amber-900 md:grid-cols-3">
              <p>金額：NT$ {transaction.deposit_total ?? transaction.payment_amount ?? "-"}</p>
              <p>狀態：{paid ? "已付款" : "待付款"}</p>
              <p className="truncate">交易編號：{transaction.rec_trade_id ?? "-"}</p>
            </div>
            {transaction.payment_note ? (
              <p className="mt-2 text-[11px] text-amber-800">{transaction.payment_note}</p>
            ) : null}
          </div>
        ) : (
          <div className="rounded-xl border border-emerald-100 bg-white/70 p-3 text-xs text-emerald-900">
            此店家免訂金，已直接確認訂位。
          </div>
        )}

        {transaction.shop_id ? (
          <Link href={`/shops/${transaction.shop_id}`}>
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
  const [mode, setMode] = useState<Mode>("recommend");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // non-agent mode (search / recommend)
  const [answer, setAnswer] = useState<string | null>(null);
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [toolUsed, setToolUsed] = useState<string | null>(null);

  // agent mode — chat history
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
    setMode("agent");
    setQuery(q);
  }, []);

  async function runSearchOrRecommend(q: string) {
    setLoading(true);
    setError(null);
    setAnswer(null);
    setHits([]);
    setToolUsed(null);
    try {
      if (mode === "search") {
        const r = await aiApi.search(q);
        setHits(r.hits);
      } else {
        const r = await aiApi.recommend(q);
        setAnswer(r.answer);
        setHits(r.hits);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "AI 服務錯誤");
    } finally {
      setLoading(false);
    }
  }

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
    if (mode === "agent") {
      sendAgentMessage(q);
    } else {
      runSearchOrRecommend(q);
    }
  }

  const modes: { key: Mode; label: string; icon: typeof Search; desc: string }[] = [
    { key: "search", label: "語意搜尋", icon: Search, desc: "向量檢索 top-K 店家" },
    { key: "recommend", label: "智能推薦", icon: Sparkles, desc: "RAG：檢索 + LLM 推薦理由" },
    { key: "agent", label: "AI Chat", icon: Bot, desc: "多輪對話 · Redis session · Function calling" },
  ];

  const renderReason = (hit: SearchHit) => {
    const parts: string[] = [];
    if (hit.category) parts.push(CATEGORY_LABELS[hit.category] ?? hit.category);
    if (hit.booking_difficulty) parts.push(hit.booking_difficulty);
    if (hit.price_per_person) parts.push(hit.price_per_person);
    else if (hit.avg_price) parts.push(`NT$ ${hit.avg_price}`);
    if (hit.hot_seat_count) parts.push(`Hot Seat ${hit.hot_seat_count} 案`);
    return parts.slice(0, 3).join(" · ");
  };

  return (
    <main className="mx-auto min-h-screen max-w-4xl px-4 py-8 md:px-8">
      <h1 className="mb-2 text-3xl font-bold">AI 搜尋</h1>
      <p className="text-muted-foreground mb-6">直接問場景，不用先懂分類。AI 會看語意、價位、預約難度、Hot Seat。</p>

      {/* Mode tabs */}
      <div className="mb-6 grid grid-cols-1 gap-3 md:grid-cols-3">
        {modes.map((m) => {
          const Icon = m.icon;
          return (
            <Card
              key={m.key}
              onClick={() => setMode(m.key)}
              className={`cursor-pointer transition ${
                mode === m.key ? "border-primary bg-accent" : "hover:shadow"
              }`}
            >
              <CardContent className="p-4">
                <Icon className="mb-2 h-5 w-5" />
                <div className="font-semibold">{m.label}</div>
                <div className="text-muted-foreground mt-1 text-xs">{m.desc}</div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Preset badges */}
      <div className="mb-4 flex flex-wrap gap-2">
        <span className="text-muted-foreground self-center text-sm">範例：</span>
        {PRESETS[mode].map((preset) => (
          <Badge
            key={preset}
            variant="outline"
            className="cursor-pointer"
            onClick={() => {
              setQuery(preset);
              handleRun(preset);
            }}
          >
            {preset}
          </Badge>
        ))}
      </div>

      {mode !== "agent" && (
        <div className="mb-6 rounded-2xl border bg-muted/30 p-4">
          <p className="text-sm font-medium">推薦問法</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {["適合約會", "高級火鍋", "商務請客", "中山站附近", "有 Hot Seat"].map((tip) => (
              <span key={tip} className="rounded-full border bg-background px-3 py-1 text-xs text-muted-foreground">
                {tip}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* ── Agent: chat UI ── */}
      {mode === "agent" ? (
        <div className="flex flex-col gap-3">
          {/* Chat history */}
          <div ref={scrollRef} className="flex flex-col gap-3 max-h-[70vh] min-h-[12rem] overflow-y-auto rounded-xl border p-4 bg-muted/20">
            {messages.length === 0 && (
              <p className="text-muted-foreground text-sm text-center mt-8">
                開始對話吧！可以問「信義區想吃火鍋」或「幫我訂明天晚上」
              </p>
            )}
            {messages.map((m, i) => (
              <div
                key={i}
                className={`flex flex-col ${m.role === "user" ? "items-end" : "items-start"}`}
              >
                <div className={m.role === "user" ? "max-w-[80%]" : "w-full"}>
                  <div
                    className={`px-3 py-2 rounded-2xl text-sm ${
                      m.role === "user"
                        ? "bg-primary text-primary-foreground rounded-br-sm whitespace-pre-wrap"
                        : "bg-muted rounded-bl-sm"
                    }`}
                  >
                    {m.role === "user" ? (
                      m.content
                    ) : (
                      <div className="prose prose-sm dark:prose-invert max-w-none">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {m.content}
                        </ReactMarkdown>
                      </div>
                    )}
                  </div>
                  {m.toolsUsed && m.toolsUsed.length > 0 && (
                    <div className="mt-1 flex flex-wrap gap-1">
                      {m.toolsUsed.map((t) => (
                        <Badge key={t} variant="secondary" className="text-[10px] px-1.5 py-0">
                          {t}
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>
                {m.shops && m.shops.length > 0 && (
                  <div className="mt-3 w-full space-y-3">
                    {m.shops.map((shop, rank) => (
                      <AgentShopCard key={shop.shop_id} shop={shop} rank={rank + 1} />
                    ))}
                  </div>
                )}
                {m.transaction ? (
                  <AgentBookingConfirmationCard transaction={m.transaction} />
                ) : null}
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="px-3 py-2 rounded-2xl text-sm bg-muted rounded-bl-sm text-muted-foreground animate-pulse">
                  思考中...
                </div>
              </div>
            )}
          </div>

          {/* Input row */}
          <div className="flex gap-2">
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="輸入你的需求..."
              onKeyDown={(e) => e.key === "Enter" && !loading && handleRun(query)}
              disabled={loading}
            />
            <Button onClick={() => handleRun(query)} disabled={loading || !query.trim()}>
              {loading ? "..." : "送出"}
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={handleClearChat}
              title="清空對話"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
          <p className="text-[10px] text-muted-foreground">
            Session：{sessionId} · Redis 30 分鐘內重整可繼續對話
          </p>
        </div>
      ) : (
        /* ── Search / Recommend: single-turn UI ── */
        <>
          <div className="mb-3 flex gap-2">
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="輸入你的需求..."
              onKeyDown={(e) => e.key === "Enter" && handleRun(query)}
            />
            <Button onClick={() => handleRun(query)} disabled={loading || !query.trim()}>
              {loading ? "..." : "送出"}
            </Button>
          </div>

          {error && (
            <Card className="mb-4 border-red-300 bg-red-50">
              <CardContent className="p-4 text-sm text-red-700">{error}</CardContent>
            </Card>
          )}

          {answer && (
            <Card className="mb-4">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Sparkles className="h-4 w-4" />
                  AI 回應
                  {toolUsed && (
                    <Badge variant="secondary" className="ml-2 text-xs">
                      tool: {toolUsed}
                    </Badge>
                  )}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="whitespace-pre-wrap">{answer}</p>
              </CardContent>
            </Card>
          )}

          {hits.length > 0 && (
            <div>
              <h3 className="mb-3 font-semibold">檢索結果</h3>
              <Separator className="mb-3" />
              <div className="space-y-3">
                {hits.map((h) => (
                  <Link key={h.shop_id} href={`/shops/${h.shop_id}`}>
                    <Card className="cursor-pointer transition hover:shadow">
                      <CardContent className="p-4">
                        {h.hot_seat_count ? (
                          <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-2.5 py-2">
                            <p className="text-[11px] font-medium text-amber-800">
                              Hot Seat 限時搶位
                            </p>
                            <p className="mt-0.5 text-[11px] text-amber-700">
                              目前有 {h.hot_seat_count} 個熱門時段方案
                            </p>
                          </div>
                        ) : null}

                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="font-medium">{h.name}</div>
                            <div className="mt-1 flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
                              {h.district ? (
                                <span className="inline-flex items-center gap-1">
                                  <MapPin className="h-3 w-3" />
                                  {h.district}
                                </span>
                              ) : null}
                              {h.district && h.mrt_station ? <span>·</span> : null}
                              {h.mrt_station ? <span>捷運{h.mrt_station}</span> : null}
                            </div>
                          </div>
                          <Badge variant="outline" className="text-xs shrink-0">
                            score {h.score.toFixed(3)}
                          </Badge>
                        </div>

                        {renderReason(h) ? (
                          <p className="mt-3 text-[11px] font-medium text-foreground/80">
                            {renderReason(h)}
                          </p>
                        ) : null}

                        <div className="mt-3 flex flex-wrap gap-1.5">
                          {h.category ? (
                            <Badge variant="secondary" className="text-[11px]">
                              {CATEGORY_LABELS[h.category] ?? h.category}
                            </Badge>
                          ) : null}
                          {(h.atmosphere_tags ?? []).slice(0, 3).map((tag) => (
                            <Badge key={`${h.shop_id}-${tag}`} variant="outline" className="text-[11px]">
                              {tag}
                            </Badge>
                          ))}
                        </div>

                        <div className="mt-3 space-y-1 text-xs text-muted-foreground">
                          {h.price_per_person ? <p>價位：{h.price_per_person}</p> : null}
                          {h.booking_difficulty ? <p>預約難度：{h.booking_difficulty}</p> : null}
                          {h.signature_dishes?.[0] ? <p>招牌菜：{h.signature_dishes[0]}</p> : null}
                        </div>
                      </CardContent>
                    </Card>
                  </Link>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </main>
  );
}
