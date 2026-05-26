"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Send, Sparkles, X } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type Hit = {
  shop_id: number;
  name: string;
  district: string;
};

type Msg = {
  role: "user" | "ai";
  content: string;
  hits?: Hit[];
  tools_used?: string[];
};

export function AiConcierge() {
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
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: msg }]);
    setLoading(true);
    try {
      const r = await fetch("/api/ai/agent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: msg, session_id: sessionId }),
      }).then((res) => res.json());
      setMessages((prev) => [
        ...prev,
        {
          role: "ai",
          content: r.answer || "",
          hits: r.hits,
          tools_used: r.tools_used,
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "ai", content: "錯誤、再試一次" },
      ]);
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
      {/* Trigger button — hidden when sidebar open */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed right-6 bottom-6 z-40 flex h-14 w-14 items-center justify-center rounded-full bg-primary text-white shadow-lg transition hover:scale-105"
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
                <p>試試問我：</p>
                <p className="mt-2">「信義區想吃火鍋」</p>
                <p>「適合約會的鐵板燒」</p>
                <p>「幫我訂明天 7 點 2 人」</p>
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
                  <div
                    className={`rounded-2xl px-4 py-2.5 text-sm ${
                      m.role === "user"
                        ? "rounded-br-sm bg-primary text-white"
                        : "rounded-bl-sm bg-muted"
                    }`}
                  >
                    {m.role === "ai" ? (
                      <div className="prose prose-sm dark:prose-invert max-w-none">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {m.content}
                        </ReactMarkdown>
                      </div>
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
                  </div>

                  {m.tools_used && m.tools_used.length > 0 && (
                    <div className="mt-1 flex flex-wrap gap-1">
                      {m.tools_used.map((t, idx) => (
                        <span
                          key={idx}
                          className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground"
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {loading && (
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
                disabled={loading}
              />
              <button
                onClick={handleSend}
                disabled={loading || !input.trim()}
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
