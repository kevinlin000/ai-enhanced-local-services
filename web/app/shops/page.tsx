"use client";

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import type { SearchHit } from "@/lib/api";
import { javaApi } from "@/lib/api";
import { getStyleByTypeId } from "@/lib/categoryStyle";
import { isLegacySeedShop } from "@/lib/legacySeedShops";
import { proxyImageUrl } from "@/lib/photoProxy";
import { getBestShopCardPhoto, getShopDataQualityScore, getShopOverview } from "@/lib/shopPhotoManifest";
import { ListFilter, MapPin, Search, Sparkles, Star, X } from "lucide-react";

// AI search via Next.js rewrite proxy /api/ai/* → http://localhost:8000/api/ai/*
const CLIENT_AI_API = "";

interface Shop {
  id: number;
  name: string;
  district?: string;
  address?: string;
  images?: string;
  score?: number;
  comments?: number;
  typeId?: number;
  mrtStation?: string;
  avgPrice?: number;
  aiCategory?: string;
  aiPricePerPerson?: string;
  aiBookingDifficulty?: string;
  aiAtmosphereTags?: string[];
  aiSignatureDishes?: string[];
  aiHotSeatCount?: number;
}

interface FilterOptions {
  types: { id: number; name: string; count: number }[];
  districts: { name: string; count: number }[];
  mrtStations: { name: string; count: number }[];
  totalShops: number;
}

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
  international: "異國料理",
  brunch: "美式料理",
  "fine-dining": "高級餐廳",
  "cafe-premium": "甜點 / 咖啡",
};

const AI_QUICK_QUERIES = [
  "中山區 商務宴請 台菜 安靜包廂",
  "大安區 約會餐廳 晚餐 氣氛好",
  "信義區 日式料理 高評價 難訂",
  "捷運站附近 火鍋 4 人聚餐",
  "今晚可訂 熱門時段 Hot Seat",
];

const SCORE_OPTIONS = [
  { label: "不限", value: null },
  { label: "4.5+", value: 45 },
  { label: "4.0+", value: 40 },
  { label: "3.5+", value: 35 },
];

const PAGE_SIZE_OPTIONS = [12, 24, 48, "all"] as const;
type PageSize = (typeof PAGE_SIZE_OPTIONS)[number];
const SEARCH_FETCH_SIZE = 2000;

function getScoreLabel(value: number | null) {
  if (value == null) return "不限";
  return `${(value / 10).toFixed(1)}+`;
}

function getDisplaySpend(shop: Shop) {
  const overview = getShopOverview(shop.id);
  if (overview?.price_overview) return `平均每人 ${overview.price_overview}`;
  if (shop.aiPricePerPerson && shop.aiPricePerPerson !== "未提及") return `價位：${shop.aiPricePerPerson}`;
  if (shop.avgPrice) return `NT$ ${shop.avgPrice}`;
  return null;
}

function sortVisibleShops(shops: Shop[]) {
  return [...shops].sort((a, b) => {
    const aSeed = isLegacySeedShop(a.id) ? 1 : 0;
    const bSeed = isLegacySeedShop(b.id) ? 1 : 0;
    if (aSeed !== bSeed) return aSeed - bSeed;
    const aQuality = getShopDataQualityScore(a.id, getFallbackImage(a), a.comments);
    const bQuality = getShopDataQualityScore(b.id, getFallbackImage(b), b.comments);
    if (bQuality !== aQuality) return bQuality - aQuality;
    return (b.score ?? 0) - (a.score ?? 0);
  });
}

function getFallbackImage(shop: Shop) {
  return shop.images?.startsWith("http") ? shop.images : null;
}

function hideLegacySeedShops(shops: Shop[]) {
  return shops.filter((shop) => !isLegacySeedShop(shop.id));
}

function ShopsPageContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [options, setOptions] = useState<FilterOptions | null>(null);
  const [shops, setShops] = useState<Shop[]>([]);
  const [loading, setLoading] = useState(true);
  const [categorySlugToId, setCategorySlugToId] = useState<Map<string, number>>(new Map());

  // search mode — lazy init from URL (?mode=ai)
  const [searchMode, setSearchMode] = useState<"text" | "ai">(() =>
    searchParams.get("mode") === "ai" ? "ai" : "text"
  );
  const [aiHitIds, setAiHitIds] = useState<number[] | null>(null);
  const [aiHitMeta, setAiHitMeta] = useState<Map<number, SearchHit>>(new Map());
  const [aiLoading, setAiLoading] = useState(false);

  // all shops cache for AI mode ordering
  const allShopsRef = useRef<Shop[]>([]);

  // filter state — lazy init from URL so F5 restores state without flash
  const [q, setQ] = useState(() => searchParams.get("q") ?? "");
  const [debouncedQ, setDebouncedQ] = useState(() => searchParams.get("q") ?? "");
  const [selectedTypes, setSelectedTypes] = useState<Set<number>>(() => {
    const raw = searchParams.get("types");
    return raw ? new Set(raw.split(",").map(Number).filter(Boolean)) : new Set();
  });
  const [selectedDistricts, setSelectedDistricts] = useState<Set<string>>(() => {
    const raw = searchParams.get("districts");
    return raw ? new Set(raw.split(",").filter(Boolean)) : new Set();
  });
  const [selectedMrt, setSelectedMrt] = useState<Set<string>>(() => {
    const raw = searchParams.get("mrt");
    return raw ? new Set(raw.split(",").filter(Boolean)) : new Set();
  });
  const [minScore, setMinScore] = useState<number | null>(null);
  const [pageSize, setPageSize] = useState<PageSize>(24);
  const [page, setPage] = useState(1);

  // skip first sync so initial URL params are not immediately overwritten
  const isFirstRender = useRef(true);

  // load filter options + all-shops cache once
  useEffect(() => {
    javaApi.shopFilterOptions().then((r) => {
      if (r?.success) setOptions(r.data);
    });
    javaApi.listCategories().then((r) => {
      const next = new Map<string, number>();
      (r?.data ?? []).forEach((category) => {
        next.set(category.slug, category.id);
      });
      setCategorySlugToId(next);
    });
    javaApi.shopSearch({ size: SEARCH_FETCH_SIZE }).then((r) => {
      if (r?.success) allShopsRef.current = hideLegacySeedShops(r.data.records ?? []);
    });
  }, []);

  // backward compat: ?category=hotpot (from home page links) → selectedTypes
  // only runs when ?types= is absent (new format already handled by lazy init)
  useEffect(() => {
    const categorySlug = searchParams.get("category");
    if (!categorySlug || searchParams.get("types") || !categorySlugToId.size) return;
    const typeId = categorySlugToId.get(categorySlug);
    if (!typeId) return;
    setSearchMode("text");
    setSelectedTypes(new Set([typeId]));
  }, [searchParams, categorySlugToId]);

  // state → URL: keep URL in sync so F5 restores full filter state
  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    const params = new URLSearchParams();
    if (selectedTypes.size) params.set("types", [...selectedTypes].join(","));
    if (selectedDistricts.size) params.set("districts", [...selectedDistricts].join(","));
    if (selectedMrt.size) params.set("mrt", [...selectedMrt].join(","));
    if (q) params.set("q", q);
    if (searchMode === "ai") params.set("mode", "ai");
    router.replace(`/shops${params.size ? "?" + params.toString() : ""}`, { scroll: false });
  }, [selectedTypes, selectedDistricts, selectedMrt, q, searchMode, router]);

  // debounce q
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(q), 300);
    return () => clearTimeout(t);
  }, [q]);

  useEffect(() => {
    setPage(1);
  }, [searchMode, debouncedQ, selectedTypes, selectedDistricts, selectedMrt, minScore, pageSize]);

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
        size: SEARCH_FETCH_SIZE,
      })
      .then((r) => {
        if (r?.success) {
          const filtered = hideLegacySeedShops(r.data.records ?? []);
          setShops(filtered);
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
        const hits: SearchHit[] = data?.hits ?? [];
        const ids: number[] = hits.map((h) => h.shop_id);
        setAiHitMeta(new Map(hits.map((hit) => [hit.shop_id, hit])));
        setAiHitIds(ids);
      })
      .catch(() => {
        setAiHitMeta(new Map());
        setAiHitIds([]);
      })
      .finally(() => setAiLoading(false));
  }, [searchMode, debouncedQ]);

  // ── AI mode: order shops by hit order ──
  useEffect(() => {
    if (searchMode !== "ai" || aiHitIds === null) return;
    if (aiHitIds.length === 0) {
      setShops([]);
      return;
    }
    const map = new Map(allShopsRef.current.map((s) => [s.id, s]));
    const ordered = aiHitIds
      .map((id) => {
        const base = map.get(id);
        const meta = aiHitMeta.get(id);
        if (!base) return null;
        return {
          ...base,
          aiCategory: meta?.category ?? undefined,
          aiPricePerPerson: meta?.price_per_person ?? undefined,
          aiBookingDifficulty: meta?.booking_difficulty ?? undefined,
          aiAtmosphereTags: meta?.atmosphere_tags ?? undefined,
          aiSignatureDishes: meta?.signature_dishes ?? undefined,
          aiHotSeatCount: meta?.hot_seat_count ?? undefined,
          avgPrice: meta?.avg_price ?? base.avgPrice,
        };
      })
      .filter(Boolean) as Shop[];
    const filtered = hideLegacySeedShops(ordered);
    setShops(filtered);
  }, [searchMode, aiHitIds, aiHitMeta]);

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

  const typeNameById = useMemo(() => {
    const map = new Map<number, string>();
    (options?.types ?? []).forEach((type) => map.set(type.id, type.name));
    return map;
  }, [options]);

  const selectedTypeOptions = useMemo(
    () =>
      [...selectedTypes].map((id) => ({
        id,
        name: typeNameById.get(id) ?? "分類載入中",
      })),
    [selectedTypes, typeNameById],
  );

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
  const visibleShops = useMemo(
    () => (searchMode === "text" ? sortVisibleShops(shops) : shops),
    [searchMode, shops],
  );
  const totalPages = useMemo(() => {
    if (pageSize === "all") return 1;
    return Math.max(1, Math.ceil(visibleShops.length / pageSize));
  }, [pageSize, visibleShops.length]);
  const pagedShops = useMemo(() => {
    if (pageSize === "all") return visibleShops;
    const start = (page - 1) * pageSize;
    return visibleShops.slice(start, start + pageSize);
  }, [pageSize, page, visibleShops]);

  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  const renderAiReason = (shop: Shop) => {
    const parts: string[] = [];
    if (shop.aiCategory) parts.push(CATEGORY_LABELS[shop.aiCategory] ?? shop.aiCategory);
    if (shop.aiBookingDifficulty && shop.aiBookingDifficulty !== "未提及") parts.push(shop.aiBookingDifficulty);
    if (shop.aiPricePerPerson && shop.aiPricePerPerson !== "未提及") parts.push(shop.aiPricePerPerson);
    else if (shop.avgPrice) parts.push(`NT$ ${shop.avgPrice}`);
    if (shop.aiHotSeatCount) parts.push(`Hot Seat ${shop.aiHotSeatCount} 案`);
    return parts.slice(0, 3).join(" · ");
  };

  return (
    <div className="max-w-7xl mx-auto px-4 md:px-8 py-6">
      {/* Header */}
      <div className="mb-5 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-2xl md:text-3xl font-semibold tracking-normal">餐廳探索</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {options?.totalShops ?? "—"} 家台北餐廳資料，依料理、區域、捷運、評價與訂位訊號快速縮小範圍。
          </p>
          <p className="mt-1 text-xs text-muted-foreground/80">
            免登入可瀏覽完整店家資訊；訂位、收藏與候補通知會在操作時要求 LINE 登入。
          </p>
        </div>

        <div className="inline-flex w-full rounded-lg border bg-background p-1 md:w-auto">
          <button
            onClick={switchToText}
            className={`flex flex-1 items-center justify-center gap-1.5 rounded-md px-3 py-1.5 text-sm transition-colors md:flex-none ${
              searchMode === "text"
                ? "bg-foreground text-background"
                : "text-muted-foreground hover:bg-muted hover:text-foreground"
            }`}
          >
            <Search className="h-4 w-4" />
            條件篩選
          </button>
          <button
            onClick={switchToAi}
            className={`flex flex-1 items-center justify-center gap-1.5 rounded-md px-3 py-1.5 text-sm transition-colors md:flex-none ${
              searchMode === "ai"
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-muted hover:text-foreground"
            }`}
          >
            <Sparkles className="h-4 w-4" />
            需求排序
          </button>
        </div>
      </div>

      {/* Search bar */}
      <div className="relative mb-4">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <input
          type="text"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={
            searchMode === "ai"
              ? "輸入決策條件，例如「中山區 商務宴請 台菜 安靜包廂」"
              : "搜尋店名、地址、行政區或捷運站"
          }
          className={`w-full rounded-lg border bg-background py-2.5 pl-10 pr-10 text-sm focus:outline-none focus:ring-2 ${
            searchMode === "ai"
              ? "border-primary/40 focus:ring-primary"
              : "focus:ring-primary"
          }`}
        />
        {q && (
          <button
            onClick={() => setQ("")}
            aria-label="清除搜尋"
            className="absolute right-3 top-1/2 -translate-y-1/2 rounded-md p-1 hover:bg-muted"
          >
            <X className="h-4 w-4 text-muted-foreground" />
          </button>
        )}
      </div>

      {searchMode === "text" && activeFilterCount > 0 ? (
        <div className="mb-5 flex flex-wrap items-center gap-2">
          {debouncedQ ? (
            <button
              onClick={() => setQ("")}
              className="inline-flex items-center gap-1 rounded-full border bg-muted/40 px-3 py-1 text-xs text-foreground"
            >
              搜尋：{debouncedQ}
              <X className="h-3 w-3" />
            </button>
          ) : null}
          {selectedTypeOptions.map((type) => (
            <button
              key={type.id}
              onClick={() => toggle(selectedTypes, setSelectedTypes, type.id)}
              className="inline-flex items-center gap-1 rounded-full border bg-muted/40 px-3 py-1 text-xs text-foreground"
            >
              {type.name}
              <X className="h-3 w-3" />
            </button>
          ))}
          {[...selectedDistricts].map((district) => (
            <button
              key={district}
              onClick={() => toggle(selectedDistricts, setSelectedDistricts, district)}
              className="inline-flex items-center gap-1 rounded-full border bg-muted/40 px-3 py-1 text-xs text-foreground"
            >
              {district}
              <X className="h-3 w-3" />
            </button>
          ))}
          {[...selectedMrt].map((station) => (
            <button
              key={station}
              onClick={() => toggle(selectedMrt, setSelectedMrt, station)}
              className="inline-flex items-center gap-1 rounded-full border bg-muted/40 px-3 py-1 text-xs text-foreground"
            >
              捷運{station}
              <X className="h-3 w-3" />
            </button>
          ))}
          {minScore ? (
            <button
              onClick={() => setMinScore(null)}
              className="inline-flex items-center gap-1 rounded-full border bg-muted/40 px-3 py-1 text-xs text-foreground"
            >
              評分 {getScoreLabel(minScore)}
              <X className="h-3 w-3" />
            </button>
          ) : null}
          <button
            onClick={clearAll}
            className="inline-flex items-center gap-1 rounded-full border border-primary/40 px-3 py-1 text-xs text-primary hover:bg-primary/5"
          >
            清除全部
          </button>
        </div>
      ) : null}

      {searchMode === "ai" && (
        <div className="mb-6">
          <div className="mb-2 flex items-center justify-between gap-3">
            <p className="text-xs font-medium tracking-normal text-primary">
              常用決策模板
            </p>
            <p className="text-[11px] text-muted-foreground">
              套用後可再調整條件
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {AI_QUICK_QUERIES.map((item) => (
              <button
                key={item}
                onClick={() => setQ(item)}
                className="rounded-full border border-primary/30 bg-primary/5 px-3 py-1.5 text-xs text-primary transition-colors hover:bg-primary/10"
              >
                {item}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-[260px_1fr] gap-6">
        {/* ── Left filter sidebar ── */}
        <aside
          className={`space-y-5 md:sticky md:top-6 md:self-start md:max-h-[calc(100vh-3rem)] md:overflow-y-auto transition-opacity ${
            searchMode === "ai" ? "opacity-40 pointer-events-none select-none" : ""
          }`}
        >
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-sm font-medium">
              <ListFilter className="h-4 w-4 text-muted-foreground" />
              篩選條件
            </div>
            {activeFilterCount > 0 ? (
              <button
                onClick={clearAll}
                className="text-xs text-primary hover:underline"
              >
                清除 {activeFilterCount}
              </button>
            ) : null}
          </div>

          {/* 評分 */}
          <div>
            <p className="mb-2 flex items-center gap-1.5 text-sm font-medium">
              <Star className="h-4 w-4 text-muted-foreground" />
              最低評分
            </p>
            <div className="grid grid-cols-2 gap-2">
              {SCORE_OPTIONS.map((opt) => (
                <button
                  key={opt.label}
                  onClick={() => setMinScore(opt.value)}
                  className={`rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
                    minScore === opt.value
                      ? "border-foreground bg-foreground text-background"
                      : "bg-background text-muted-foreground hover:bg-muted hover:text-foreground"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* 分類 */}
          {options && (
            <div>
              <p className="mb-2 text-sm font-medium">餐廳分類</p>
              <div className="grid grid-cols-1 gap-2">
                {options.types.map((t) => {
                  const style = getStyleByTypeId(t.id);
                  const Icon = style.icon;
                  const active = selectedTypes.has(t.id);
                  return (
                    <button
                      key={t.id}
                      onClick={() => toggle(selectedTypes, setSelectedTypes, t.id)}
                      aria-pressed={active}
                      className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
                        active
                          ? "border-foreground bg-foreground text-background"
                          : "bg-background text-foreground hover:bg-muted"
                      }`}
                    >
                      <span
                        className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-md ${
                          active ? "bg-background/15" : "bg-muted"
                        }`}
                      >
                        <Icon className="h-4 w-4" strokeWidth={1.75} />
                      </span>
                      <span className="min-w-0 flex-1 truncate">{t.name}</span>
                      <span
                        className={`text-xs ${
                          active ? "text-background/75" : "text-muted-foreground"
                        }`}
                      >
                        {t.count}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* 區域 */}
          {options && (
            <div>
              <p className="mb-2 text-sm font-medium">區域</p>
              <div className="space-y-1.5">
                {options.districts.map((d) => (
                  <button
                    key={d.name}
                    onClick={() =>
                      toggle(selectedDistricts, setSelectedDistricts, d.name)
                    }
                    aria-pressed={selectedDistricts.has(d.name)}
                    className={`flex w-full items-center gap-2 rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
                      selectedDistricts.has(d.name)
                        ? "border-foreground bg-foreground text-background"
                        : "bg-background hover:bg-muted"
                    }`}
                  >
                    <span className="flex-1">{d.name}</span>
                    <span
                      className={`text-xs ${
                        selectedDistricts.has(d.name)
                          ? "text-background/75"
                          : "text-muted-foreground"
                      }`}
                    >
                      {d.count}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* 捷運站 */}
          {options && (
            <div>
              <p className="mb-2 text-sm font-medium">捷運站</p>
              <div className="space-y-1.5">
                {options.mrtStations.map((m) => (
                  <button
                    key={m.name}
                    onClick={() =>
                      toggle(selectedMrt, setSelectedMrt, m.name)
                    }
                    aria-pressed={selectedMrt.has(m.name)}
                    className={`flex w-full items-center gap-2 rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
                      selectedMrt.has(m.name)
                        ? "border-foreground bg-foreground text-background"
                        : "bg-background hover:bg-muted"
                    }`}
                  >
                    <span className="flex-1">{m.name}</span>
                    <span
                      className={`text-xs ${
                        selectedMrt.has(m.name)
                          ? "text-background/75"
                          : "text-muted-foreground"
                      }`}
                    >
                      {m.count}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </aside>

        {/* ── Right results ── */}
        <div>
          <div className="flex items-baseline justify-between mb-3">
            <p className="text-sm text-muted-foreground">
              {isLoading ? "搜尋中..." : `目前顯示 ${visibleShops.length} 家`}
              {activeFilterCount > 0 && (
                <span> · {activeFilterCount} 個篩選</span>
              )}
            </p>
            {!isLoading && visibleShops.length > 0 ? (
              <div className="flex items-center gap-2 text-xs">
                <span className="text-muted-foreground">每頁顯示</span>
                <div className="flex items-center gap-1 rounded-lg border bg-background p-1">
                  {PAGE_SIZE_OPTIONS.map((option) => {
                    const active = pageSize === option;
                    const label = option === "all" ? "全部" : String(option);
                    return (
                      <button
                        key={label}
                        onClick={() => setPageSize(option)}
                        className={`rounded-md px-2 py-1 transition-colors ${
                          active
                            ? "bg-foreground text-background"
                            : "text-muted-foreground hover:bg-muted"
                        }`}
                      >
                        {label}
                      </button>
                    );
                  })}
                </div>
              </div>
            ) : null}
          </div>

          {/* AI mode hint */}
          {searchMode === "ai" && debouncedQ && !aiLoading && (
            <div className="mb-4 rounded-lg border border-primary/20 bg-primary/5 px-4 py-3">
              <p className="text-xs text-primary">
                需求排序會先比對地點、料理與用餐目的，再參考價位、預約難度、熱門時段與招牌菜。
              </p>
              <p className="mt-1 text-[11px] text-muted-foreground">
                目前條件：{debouncedQ}
              </p>
            </div>
          )}

          {visibleShops.length === 0 && !isLoading && (
            <div className="text-center py-12 text-muted-foreground text-sm">
              {searchMode === "ai" && debouncedQ
                ? "沒有匹配這組需求的餐廳資料"
                : "沒有符合條件的店家"}
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 items-start">
            {pagedShops.map((shop) => {
              const style = getStyleByTypeId(shop.typeId);
              const Icon = style.icon;
              const coverPhoto = proxyImageUrl(
                getBestShopCardPhoto(shop.id, getFallbackImage(shop)),
              );
              const displaySpend = getDisplaySpend(shop);
              const topTags = (shop.aiAtmosphereTags ?? []).slice(0, 2);
              const topDish = shop.aiSignatureDishes?.[0];
              return (
                <Link
                  key={shop.id}
                  href={`/shops/${shop.id}`}
                  className="group block"
                >
                  <div className="bb-premium-surface overflow-hidden rounded-lg transition-colors group-hover:border-[rgb(167_137_67_/_0.42)]">
                    <div className={`relative aspect-[4/3] overflow-hidden bg-gradient-to-br ${style.gradient}`}>
                      {coverPhoto ? (
                        <>
                          <img
                            src={coverPhoto}
                            alt={`${shop.name}-cover`}
                            className="h-full w-full object-cover"
                            loading="lazy"
                          />
                          <div className="absolute inset-0 bg-gradient-to-t from-black/55 via-black/10 to-transparent" />
                        </>
                      ) : (
                        <div className="flex h-full items-center justify-center">
                          <Icon
                            className="h-10 w-10 text-foreground/40"
                            strokeWidth={1.5}
                          />
                        </div>
                      )}
                      <div className="absolute left-3 top-3 rounded-full bg-[rgb(255_253_248_/_0.88)] px-2.5 py-1 text-[11px] font-medium text-[var(--bb-ink)] backdrop-blur">
                        {style.label}
                      </div>
                      {shop.score != null ? (
                        <div className="absolute bottom-3 right-3 rounded-full bg-[rgb(21_19_15_/_0.82)] px-2.5 py-1 font-mono text-xs text-white backdrop-blur">
                          {(shop.score / 10).toFixed(1)}
                        </div>
                      ) : null}
                    </div>
                    <div className="p-3.5">
                      {searchMode === "ai" && shop.aiHotSeatCount ? (
                        <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-2.5 py-2">
                          <p className="text-[11px] font-medium text-amber-800">
                            Hot Seat 限時搶位
                          </p>
                          <p className="mt-0.5 text-[11px] text-amber-700">
                            此店目前有 {shop.aiHotSeatCount} 個熱門時段方案
                          </p>
                        </div>
                      ) : null}

                      <div className="mb-1 flex items-start justify-between gap-2">
                        <h3 className="flex-1 text-[15px] font-medium leading-tight text-[var(--bb-ink)]">
                          {shop.name}
                        </h3>
                      </div>
                      <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
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

                      {displaySpend ? (
                        <div className="mt-2 text-xs font-medium text-[var(--bb-gold)]">
                          {displaySpend}
                        </div>
                      ) : null}

                      {searchMode === "ai" && renderAiReason(shop) ? (
                        <p className="mt-2 text-[11px] font-medium text-foreground/80">
                          {renderAiReason(shop)}
                        </p>
                      ) : null}

                      {searchMode === "ai" && (
                        <>
                          <div className="mt-3 flex flex-wrap gap-1.5">
                            {shop.aiCategory ? (
                              <span className="rounded-full bg-muted px-2 py-0.5 text-[11px] text-foreground/80">
                                {CATEGORY_LABELS[shop.aiCategory] ?? shop.aiCategory}
                              </span>
                            ) : null}
                            {topTags.map((tag) => (
                              <span
                                key={tag}
                                className="rounded-full bg-primary/10 px-2 py-0.5 text-[11px] text-primary"
                              >
                                {tag}
                              </span>
                            ))}
                            {shop.aiHotSeatCount ? (
                              <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] text-amber-800">
                                Hot Seat {shop.aiHotSeatCount} 案
                              </span>
                            ) : null}
                          </div>

                          <div className="mt-3 space-y-1 text-xs text-muted-foreground">
                            {shop.aiBookingDifficulty && shop.aiBookingDifficulty !== "未提及" ? (
                              <p>預約難度：{shop.aiBookingDifficulty}</p>
                            ) : null}
                            {topDish ? (
                              <p>招牌菜：{topDish}</p>
                            ) : null}
                          </div>

                          {(shop.aiAtmosphereTags?.length || 0) > 0 ? (
                            <div className="mt-3 flex flex-wrap gap-1.5">
                              {shop.aiAtmosphereTags?.slice(0, 3).map((tag) => (
                                <span
                                  key={`${shop.id}-${tag}`}
                                  className="rounded-md bg-secondary px-2 py-1 text-[11px] text-secondary-foreground"
                                >
                                  {tag}
                                </span>
                              ))}
                            </div>
                          ) : null}
                        </>
                      )}

                      <div className="mt-4 border-t border-[rgb(222_216_203_/_0.72)] pt-3 text-xs font-medium text-muted-foreground transition-colors group-hover:text-[var(--bb-gold)]">
                        查看完整資料
                      </div>
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>

          {!isLoading && visibleShops.length > 0 && pageSize !== "all" ? (
            <div className="mt-6 flex items-center justify-between gap-3 rounded-lg border bg-background px-4 py-3 text-sm">
              <p className="text-muted-foreground">
                第 {page} / {totalPages} 頁
              </p>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPage((current) => Math.max(1, current - 1))}
                  disabled={page === 1}
                  className="rounded-lg border px-3 py-1.5 text-sm disabled:cursor-not-allowed disabled:opacity-40"
                >
                  上一頁
                </button>
                <button
                  onClick={() =>
                    setPage((current) => Math.min(totalPages, current + 1))
                  }
                  disabled={page === totalPages}
                  className="rounded-lg border px-3 py-1.5 text-sm disabled:cursor-not-allowed disabled:opacity-40"
                >
                  下一頁
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export default function ShopsPage() {
  return (
    <Suspense fallback={<div className="max-w-7xl mx-auto px-4 md:px-8 py-6 text-sm text-muted-foreground">載入店家中...</div>}>
      <ShopsPageContent />
    </Suspense>
  );
}
