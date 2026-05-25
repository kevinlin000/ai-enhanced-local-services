"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { javaApi } from "@/lib/api";
import { getStyleByTypeId } from "@/lib/categoryStyle";
import { MapPin, Search, X } from "lucide-react";

// AI search via Python service proxy (avoids HTTPS→HTTP mixed content)
const CLIENT_AI_API = "/api/python";

interface Shop {
  id: number;
  name: string;
  district?: string;
  address?: string;
  score?: number;
  comments?: number;
  typeId?: number;
  mrtStation?: string;
  avgPrice?: number;
}

interface FilterOptions {
  types: { id: number; name: string; count: number }[];
  districts: { name: string; count: number }[];
  mrtStations: { name: string; count: number }[];
  totalShops: number;
}

const SCORE_OPTIONS = [
  { label: "不限", value: null },
  { label: "4.5+", value: 45 },
  { label: "4.0+", value: 40 },
  { label: "3.5+", value: 35 },
];

export default function ShopsPage() {
  const [options, setOptions] = useState<FilterOptions | null>(null);
  const [shops, setShops] = useState<Shop[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);

  // search mode
  const [searchMode, setSearchMode] = useState<"text" | "ai">("text");
  const [aiHitIds, setAiHitIds] = useState<number[] | null>(null);
  const [aiLoading, setAiLoading] = useState(false);

  // all shops cache for AI mode ordering
  const allShopsRef = useRef<Shop[]>([]);

  // filter state
  const [q, setQ] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [selectedTypes, setSelectedTypes] = useState<Set<number>>(new Set());
  const [selectedDistricts, setSelectedDistricts] = useState<Set<string>>(new Set());
  const [selectedMrt, setSelectedMrt] = useState<Set<string>>(new Set());
  const [minScore, setMinScore] = useState<number | null>(null);

  // load filter options + all-shops cache once
  useEffect(() => {
    javaApi.shopFilterOptions().then((r) => {
      if (r?.success) setOptions(r.data);
    });
    javaApi.shopSearch({ size: 100 }).then((r) => {
      if (r?.success) allShopsRef.current = r.data.records ?? [];
    });
  }, []);

  // debounce q
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(q), 300);
    return () => clearTimeout(t);
  }, [q]);

  // ── Text mode search ──
  useEffect(() => {
    if (searchMode !== "text") return;
    setLoading(true);
    javaApi
      .shopSearch({
        q: debouncedQ || undefined,
        typeIds: selectedTypes.size > 0 ? Array.from(selectedTypes) : undefined,
        districts:
          selectedDistricts.size > 0 ? Array.from(selectedDistricts) : undefined,
        mrtStations: selectedMrt.size > 0 ? Array.from(selectedMrt) : undefined,
        minScore: minScore ?? undefined,
        page: 1,
        size: 60,
      })
      .then((r) => {
        if (r?.success) {
          setShops(r.data.records ?? []);
          setTotal(r.data.total ?? 0);
        }
      })
      .finally(() => setLoading(false));
  }, [searchMode, debouncedQ, selectedTypes, selectedDistricts, selectedMrt, minScore]);

  // ── AI mode: call Python search ──
  useEffect(() => {
    if (searchMode !== "ai") return;
    if (!debouncedQ.trim()) {
      setAiHitIds(null);
      // show all shops when query cleared
      setShops(allShopsRef.current);
      setTotal(allShopsRef.current.length);
      return;
    }
    setAiLoading(true);
    fetch(`${CLIENT_AI_API}/api/ai/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: debouncedQ, top_k: 10 }),
    })
      .then((r) => r.json())
      .then((data) => {
        const ids: number[] = data?.hits?.map((h: { shop_id: number }) => h.shop_id) ?? [];
        setAiHitIds(ids);
      })
      .catch(() => setAiHitIds([]))
      .finally(() => setAiLoading(false));
  }, [searchMode, debouncedQ]);

  // ── AI mode: order shops by hit order ──
  useEffect(() => {
    if (searchMode !== "ai" || aiHitIds === null) return;
    if (aiHitIds.length === 0) {
      setShops([]);
      setTotal(0);
      return;
    }
    const map = new Map(allShopsRef.current.map((s) => [s.id, s]));
    const ordered = aiHitIds
      .map((id) => map.get(id))
      .filter((s): s is Shop => s !== undefined);
    setShops(ordered);
    setTotal(ordered.length);
  }, [searchMode, aiHitIds]);

  // switch to text mode: reset AI state, keep filter state
  const switchToText = () => {
    setSearchMode("text");
    setAiHitIds(null);
    setQ("");
  };

  // switch to AI mode: reset filter state
  const switchToAi = () => {
    setSearchMode("ai");
    setSelectedTypes(new Set());
    setSelectedDistricts(new Set());
    setSelectedMrt(new Set());
    setMinScore(null);
    setQ("");
    // show all while waiting
    setShops(allShopsRef.current);
    setTotal(allShopsRef.current.length);
  };

  const activeFilterCount = useMemo(() => {
    if (searchMode === "ai") return 0;
    let c = 0;
    if (debouncedQ) c++;
    c += selectedTypes.size;
    c += selectedDistricts.size;
    c += selectedMrt.size;
    if (minScore) c++;
    return c;
  }, [searchMode, debouncedQ, selectedTypes, selectedDistricts, selectedMrt, minScore]);

  const clearAll = () => {
    setQ("");
    setSelectedTypes(new Set());
    setSelectedDistricts(new Set());
    setSelectedMrt(new Set());
    setMinScore(null);
  };

  const toggle = <T,>(set: Set<T>, setter: (s: Set<T>) => void, item: T) => {
    const next = new Set(set);
    if (next.has(item)) next.delete(item);
    else next.add(item);
    setter(next);
  };

  const isLoading = loading || aiLoading;

  return (
    <div className="max-w-7xl mx-auto px-4 md:px-8 py-6">
      {/* Header */}
      <div className="mb-4">
        <h1 className="text-2xl md:text-3xl font-bold">探索店家</h1>
        <p className="text-sm text-muted-foreground mt-1">
          73 家台北中高價餐廳、含 AI 評論摘要
        </p>
      </div>

      {/* Mode toggle */}
      <div className="flex gap-2 mb-4">
        <button
          onClick={switchToText}
          className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${
            searchMode === "text"
              ? "bg-foreground text-background border-foreground"
              : "bg-background hover:bg-muted"
          }`}
        >
          🔍 字串搜尋
        </button>
        <button
          onClick={switchToAi}
          className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${
            searchMode === "ai"
              ? "bg-primary text-primary-foreground border-primary"
              : "bg-background hover:bg-muted"
          }`}
        >
          ✨ AI 語意搜尋
        </button>
      </div>

      {/* Search bar */}
      <div className="relative mb-6">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <input
          type="text"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={
            searchMode === "ai"
              ? "用自然語言描述、例如「適合約會的鐵板燒」"
              : "搜尋店名、地址、區域..."
          }
          className={`w-full pl-10 pr-10 py-2.5 border rounded-lg text-sm focus:outline-none focus:ring-2 bg-background ${
            searchMode === "ai"
              ? "focus:ring-primary border-primary/40"
              : "focus:ring-primary"
          }`}
        />
        {q && (
          <button
            onClick={() => setQ("")}
            className="absolute right-3 top-1/2 -translate-y-1/2"
          >
            <X className="h-4 w-4 text-muted-foreground" />
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-[260px_1fr] gap-6">
        {/* ── Left filter sidebar ── */}
        <aside
          className={`space-y-5 md:sticky md:top-6 md:self-start md:max-h-[calc(100vh-3rem)] md:overflow-y-auto transition-opacity ${
            searchMode === "ai" ? "opacity-40 pointer-events-none select-none" : ""
          }`}
        >
          {activeFilterCount > 0 && (
            <button
              onClick={clearAll}
              className="w-full text-xs text-primary border border-primary rounded-lg px-3 py-2 hover:bg-primary/5"
            >
              清除 {activeFilterCount} 個篩選
            </button>
          )}

          {/* 評分 */}
          <div>
            <p className="text-sm font-medium mb-2">最低評分</p>
            <div className="space-y-1">
              {SCORE_OPTIONS.map((opt) => (
                <label
                  key={opt.label}
                  className="flex items-center gap-2 cursor-pointer text-sm"
                >
                  <input
                    type="radio"
                    name="minScore"
                    checked={minScore === opt.value}
                    onChange={() => setMinScore(opt.value)}
                    className="accent-primary"
                  />
                  <span>{opt.label}</span>
                </label>
              ))}
            </div>
          </div>

          {/* 分類 */}
          {options && (
            <div>
              <p className="text-sm font-medium mb-2">分類</p>
              <div className="space-y-1 max-h-64 overflow-y-auto">
                {options.types.map((t) => (
                  <label
                    key={t.id}
                    className="flex items-center gap-2 cursor-pointer text-sm"
                  >
                    <input
                      type="checkbox"
                      checked={selectedTypes.has(t.id)}
                      onChange={() =>
                        toggle(selectedTypes, setSelectedTypes, t.id)
                      }
                      className="accent-primary"
                    />
                    <span className="flex-1">{t.name}</span>
                    <span className="text-xs text-muted-foreground">{t.count}</span>
                  </label>
                ))}
              </div>
            </div>
          )}

          {/* 區域 */}
          {options && (
            <div>
              <p className="text-sm font-medium mb-2">區域</p>
              <div className="space-y-1">
                {options.districts.map((d) => (
                  <label
                    key={d.name}
                    className="flex items-center gap-2 cursor-pointer text-sm"
                  >
                    <input
                      type="checkbox"
                      checked={selectedDistricts.has(d.name)}
                      onChange={() =>
                        toggle(selectedDistricts, setSelectedDistricts, d.name)
                      }
                      className="accent-primary"
                    />
                    <span className="flex-1">{d.name}</span>
                    <span className="text-xs text-muted-foreground">{d.count}</span>
                  </label>
                ))}
              </div>
            </div>
          )}

          {/* 捷運站 */}
          {options && (
            <div>
              <p className="text-sm font-medium mb-2">捷運站</p>
              <div className="space-y-1">
                {options.mrtStations.map((m) => (
                  <label
                    key={m.name}
                    className="flex items-center gap-2 cursor-pointer text-sm"
                  >
                    <input
                      type="checkbox"
                      checked={selectedMrt.has(m.name)}
                      onChange={() =>
                        toggle(selectedMrt, setSelectedMrt, m.name)
                      }
                      className="accent-primary"
                    />
                    <span className="flex-1">{m.name}</span>
                    <span className="text-xs text-muted-foreground">{m.count}</span>
                  </label>
                ))}
              </div>
            </div>
          )}
        </aside>

        {/* ── Right results ── */}
        <div>
          <div className="flex items-baseline justify-between mb-3">
            <p className="text-sm text-muted-foreground">
              {isLoading ? "搜尋中..." : `共 ${total} 家`}
              {activeFilterCount > 0 && (
                <span> · {activeFilterCount} 個篩選</span>
              )}
            </p>
          </div>

          {/* AI mode hint */}
          {searchMode === "ai" && debouncedQ && !aiLoading && (
            <p className="text-xs text-primary mb-3 flex items-center gap-1">
              ✨ AI 依語意排序、不套用左欄篩選
            </p>
          )}

          {shops.length === 0 && !isLoading && (
            <div className="text-center py-12 text-muted-foreground text-sm">
              {searchMode === "ai" && debouncedQ
                ? "AI 未找到相符店家"
                : "沒有符合條件的店家"}
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {shops.map((shop) => {
              const style = getStyleByTypeId(shop.typeId);
              const Icon = style.icon;
              return (
                <Link
                  key={shop.id}
                  href={`/shops/${shop.id}`}
                  className="block"
                >
                  <div className="border rounded-xl overflow-hidden hover:shadow-md transition-shadow h-full">
                    <div
                      className={`bg-gradient-to-br ${style.gradient} h-24 flex items-center justify-center`}
                    >
                      <Icon
                        className="h-10 w-10 text-foreground/40"
                        strokeWidth={1.5}
                      />
                    </div>
                    <div className="p-3">
                      <div className="flex items-start justify-between gap-2 mb-1">
                        <h3 className="font-medium text-sm leading-tight flex-1">
                          {shop.name}
                        </h3>
                        {shop.score != null && (
                          <span className="text-xs font-mono bg-foreground text-background px-1.5 py-0.5 rounded shrink-0">
                            {(shop.score / 10).toFixed(1)}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-1.5 text-xs text-muted-foreground flex-wrap">
                        {shop.district && (
                          <span className="flex items-center gap-0.5">
                            <MapPin className="h-3 w-3" />
                            {shop.district}
                          </span>
                        )}
                        {shop.district && shop.mrtStation && <span>·</span>}
                        {shop.mrtStation && (
                          <span>捷運{shop.mrtStation}</span>
                        )}
                      </div>
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
