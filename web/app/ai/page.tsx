"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Bot, Search, Sparkles, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { aiApi, type SearchHit } from "@/lib/api";

const AI_API = "";

type Mode = "search" | "recommend" | "agent";

interface Msg {
  role: "user" | "ai";
  content: string;
  hits?: SearchHit[];
  toolsUsed?: string[];
}

const PRESETS: Record<Mode, string[]> = {
  search: ["中山區的店", "市政府站附近", "想喝手搖飲"],
  recommend: ["中山區想喝手搖飲", "晚上想吃宵夜", "想吃便宜的牛肉麵"],
  agent: ["信義區想吃火鍋", "中山站附近推薦", "幫我訂明天晚上 7 點 2 人"],
};

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
  const chatBottomRef = useRef<HTMLDivElement>(null);

  // scroll to bottom on new message
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

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
    setMessages((prev) => [...prev, { role: "user", content: userMsg }]);
    setQuery("");
    setLoading(true);
    try {
      const r = await fetch(`${AI_API}/api/ai/agent`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: userMsg, session_id: sessionId }),
      }).then((res) => res.json());

      setMessages((prev) => [
        ...prev,
        {
          role: "ai",
          content: r.answer || "（無回應）",
          toolsUsed: r.tools_used,
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "ai", content: "出錯了，再試一次" },
      ]);
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

  return (
    <main className="mx-auto min-h-screen max-w-4xl px-4 py-8 md:px-8">
      <h1 className="mb-2 text-3xl font-bold">AI 搜尋</h1>
      <p className="text-muted-foreground mb-6">三種 AI 能力 demo</p>

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

      {/* ── Agent: chat UI ── */}
      {mode === "agent" ? (
        <div className="flex flex-col gap-3">
          {/* Chat history */}
          <div className="flex flex-col gap-3 max-h-[28rem] min-h-[12rem] overflow-y-auto rounded-xl border p-4 bg-muted/20">
            {messages.length === 0 && (
              <p className="text-muted-foreground text-sm text-center mt-8">
                開始對話吧！可以問「信義區想吃火鍋」或「幫我訂明天晚上」
              </p>
            )}
            {messages.map((m, i) => (
              <div
                key={i}
                className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div className={`max-w-[80%] ${m.role === "user" ? "" : ""}`}>
                  <div
                    className={`px-3 py-2 rounded-2xl text-sm whitespace-pre-wrap ${
                      m.role === "user"
                        ? "bg-primary text-primary-foreground rounded-br-sm"
                        : "bg-muted rounded-bl-sm"
                    }`}
                  >
                    {m.content}
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
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="px-3 py-2 rounded-2xl text-sm bg-muted rounded-bl-sm text-muted-foreground animate-pulse">
                  思考中...
                </div>
              </div>
            )}
            <div ref={chatBottomRef} />
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
              <div className="space-y-2">
                {hits.map((h) => (
                  <Link key={h.shop_id} href={`/shops/${h.shop_id}`}>
                    <Card className="cursor-pointer transition hover:shadow">
                      <CardContent className="flex items-center justify-between p-3">
                        <div>
                          <div className="font-medium">{h.name}</div>
                          <div className="text-muted-foreground text-xs">
                            {h.district} · 捷運{h.mrt_station}站
                          </div>
                        </div>
                        <Badge variant="outline" className="text-xs">
                          score {h.score.toFixed(3)}
                        </Badge>
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
