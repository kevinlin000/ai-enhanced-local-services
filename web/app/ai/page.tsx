"use client";

import Link from "next/link";
import { useState } from "react";
import { Bot, Search, Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { aiApi, type SearchHit } from "@/lib/api";

type Mode = "search" | "recommend" | "agent";

const PRESETS: Record<Mode, string[]> = {
  search: ["中山區的店", "市政府站附近", "想喝手搖飲"],
  recommend: ["中山區想喝手搖飲", "晚上想吃宵夜", "想吃便宜的牛肉麵"],
  agent: ["市政府站附近吃午餐", "想喝有特色的手搖飲", "今天天氣如何"],
};

export default function AiPage() {
  const [mode, setMode] = useState<Mode>("recommend");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [answer, setAnswer] = useState<string | null>(null);
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [toolUsed, setToolUsed] = useState<string | null>(null);

  async function run(q: string) {
    if (!q.trim()) return;
    setLoading(true);
    setError(null);
    setAnswer(null);
    setHits([]);
    setToolUsed(null);

    try {
      if (mode === "search") {
        const r = await aiApi.search(q);
        setHits(r.hits);
      } else if (mode === "recommend") {
        const r = await aiApi.recommend(q);
        setAnswer(r.answer);
        setHits(r.hits);
      } else {
        const r = await aiApi.agent(q);
        setAnswer(r.answer);
        setToolUsed(r.tool_used);
      }
    } catch (e) {
      const message = e instanceof Error ? e.message : "AI 服務錯誤";
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  const modes: { key: Mode; label: string; icon: typeof Search; desc: string }[] = [
    { key: "search", label: "語意搜尋", icon: Search, desc: "向量檢索 top-K 店家" },
    {
      key: "recommend",
      label: "智能推薦",
      icon: Sparkles,
      desc: "RAG 完整閉環：檢索 + LLM 推薦理由",
    },
    {
      key: "agent",
      label: "AI Agent",
      icon: Bot,
      desc: "LLM 自動決定 tool（GEO / 語意）",
    },
  ];

  return (
    <main className="mx-auto min-h-screen max-w-4xl p-8">
      <h1 className="mb-2 text-3xl font-bold">AI 搜尋</h1>
      <p className="text-muted-foreground mb-6">三種 AI 能力 demo</p>

      <div className="mb-6 grid grid-cols-1 gap-3 md:grid-cols-3">
        {modes.map((m) => {
          const Icon = m.icon;
          return (
            <Card
              key={m.key}
              onClick={() => setMode(m.key)}
              className={`cursor-pointer transition ${mode === m.key ? "border-primary bg-accent" : "hover:shadow"}`}
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

      <div className="mb-3 flex gap-2">
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="輸入你的需求..."
          onKeyDown={(e) => e.key === "Enter" && run(query)}
        />
        <Button onClick={() => run(query)} disabled={loading || !query.trim()}>
          {loading ? "..." : "送出"}
        </Button>
      </div>

      <div className="mb-6 flex flex-wrap gap-2">
        <span className="text-muted-foreground self-center text-sm">範例：</span>
        {PRESETS[mode].map((preset) => (
          <Badge
            key={preset}
            variant="outline"
            className="cursor-pointer"
            onClick={() => {
              setQuery(preset);
              run(preset);
            }}
          >
            {preset}
          </Badge>
        ))}
      </div>

      {error ? (
        <Card className="mb-4 border-red-300 bg-red-50">
          <CardContent className="p-4 text-sm text-red-700">{error}</CardContent>
        </Card>
      ) : null}

      {answer ? (
        <Card className="mb-4">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Sparkles className="h-4 w-4" />
              AI 回應
              {toolUsed ? (
                <Badge variant="secondary" className="ml-2 text-xs">
                  tool: {toolUsed}
                </Badge>
              ) : null}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="whitespace-pre-wrap">{answer}</p>
          </CardContent>
        </Card>
      ) : null}

      {hits.length > 0 ? (
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
      ) : null}
    </main>
  );
}
