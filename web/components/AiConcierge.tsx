"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { type SearchHit } from "@/lib/api";
import { Loader2, Send, Sparkles } from "lucide-react";

type Message = {
  role: "user" | "assistant";
  content: string;
  hits?: SearchHit[];
  toolsUsed?: string[];
};

const PRESETS = [
  "中山區想喝手搖飲",
  "市政府站附近吃午餐",
  "晚上想吃宵夜",
];

export function AiConcierge() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
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

  async function ask(query: string) {
    if (!query.trim() || loading) return;

    const userMsg = query.trim();
    setLoading(true);
    setMessages((prev) => [...prev, { role: "user", content: userMsg }]);
    setInput("");

    try {
      const r = await fetch("/api/ai/agent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: userMsg, session_id: sessionId }),
      }).then((res) => res.json());

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: r.answer || "（無回應）",
          hits: r.hits,
          toolsUsed: r.tools_used,
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "抱歉、AI 服務暫時無法回應。" },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="fixed right-4 bottom-4 z-40 flex h-12 w-12 items-center justify-center rounded-full border border-white/20 bg-linear-to-br from-primary to-emerald-500 text-primary-foreground shadow-[0_12px_30px_rgba(23,110,55,0.35)] transition hover:scale-105 hover:shadow-[0_16px_38px_rgba(23,110,55,0.42)] md:right-6 md:bottom-6 md:h-14 md:w-14"
        aria-label="AI Concierge"
      >
        <Sparkles className="h-5 w-5 md:h-6 md:w-6" />
      </button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="flex h-[90vh] max-w-md flex-col gap-0 overflow-hidden border-foreground/10 p-0 md:h-[600px]">
          {/* Header — shrink-0 so it never gets squeezed */}
          <DialogHeader className="bg-muted/50 shrink-0 border-b px-6 py-4">
            <DialogTitle className="flex items-center gap-2 text-lg">
              <Sparkles className="text-primary h-5 w-5" />
              AI Concierge
              <Badge variant="outline" className="font-mono ml-1 text-xs">
                Agent · Gemini
              </Badge>
            </DialogTitle>
          </DialogHeader>

          {/* Scroll area — flex-1 + min-h-0 critical for overflow in flex column */}
          <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto px-6 py-4">
            {messages.length === 0 ? (
              <div className="text-muted-foreground py-12 text-center">
                <p className="mb-2 text-sm font-medium text-foreground">今晚想吃什麼？</p>
                <p className="mb-4 text-sm">問我任何關於台北店家的問題</p>
                <div className="flex flex-wrap justify-center gap-2">
                  {PRESETS.map((preset) => (
                    <Badge
                      key={preset}
                      variant="outline"
                      className="cursor-pointer hover:bg-accent"
                      onClick={() => ask(preset)}
                    >
                      {preset}
                    </Badge>
                  ))}
                </div>
              </div>
            ) : null}

            <div className="space-y-4">
              {messages.map((message, index) => (
                <div
                  key={`${message.role}-${index}`}
                  className={message.role === "user" ? "flex justify-end" : "flex justify-start"}
                >
                  <div className="max-w-[80%]">
                    <div
                      className={`rounded-2xl px-4 py-3 text-sm ${
                        message.role === "user"
                          ? "bg-primary text-primary-foreground rounded-br-sm"
                          : "bg-muted rounded-bl-sm"
                      }`}
                    >
                      <div className="whitespace-pre-wrap leading-6">{message.content}</div>
                      {message.hits && message.hits.length > 0 ? (
                        <div className="mt-3 space-y-1 border-t border-current/10 pt-3">
                          {message.hits.slice(0, 3).map((hit) => (
                            <Link
                              key={hit.shop_id}
                              href={`/shops/${hit.shop_id}`}
                              className="block text-xs opacity-80 transition hover:underline"
                            >
                              → {hit.name} · {hit.district}
                            </Link>
                          ))}
                        </div>
                      ) : null}
                    </div>
                    {message.toolsUsed && message.toolsUsed.length > 0 ? (
                      <div className="mt-1 flex flex-wrap gap-1">
                        {message.toolsUsed.map((t) => (
                          <Badge key={t} variant="secondary" className="px-1.5 py-0 text-[10px]">
                            {t}
                          </Badge>
                        ))}
                      </div>
                    ) : null}
                  </div>
                </div>
              ))}

              {loading ? (
                <div className="flex justify-start">
                  <div className="bg-muted flex items-center gap-2 rounded-2xl px-4 py-2 text-sm">
                    <Loader2 className="h-3 w-3 animate-spin" />
                    思考中...
                  </div>
                </div>
              ) : null}
            </div>
          </div>

          {/* Footer — shrink-0 so it never gets pushed out */}
          <div className="shrink-0 border-t px-6 py-4">
            <div className="flex gap-2">
              <Input
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder="輸入你想吃什麼..."
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !loading) ask(input);
                }}
                disabled={loading}
              />
              <Button
                onClick={() => ask(input)}
                disabled={loading || !input.trim()}
                size="icon"
              >
                <Send className="h-4 w-4" />
              </Button>
            </div>
            <p className="text-muted-foreground mt-2 text-center text-xs">
              Powered by Gemini · Redis session · multi-turn
            </p>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
