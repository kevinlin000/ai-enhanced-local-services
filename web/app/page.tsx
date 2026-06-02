import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Bell, Bot, CalendarCheck, Heart, Sparkles } from "lucide-react";
import { aiApi, javaApi, type Category, type Shop, type ShopAiMetadata } from "@/lib/api";
import { getCategoryStyle, getStyleByTypeId } from "@/lib/categoryStyle";
import { isLegacySeedShop } from "@/lib/legacySeedShops";
import { proxyImageUrl } from "@/lib/photoProxy";
import { getBestShopCardPhoto, getShopOverview } from "@/lib/shopPhotoManifest";

const HOT_STATIONS = [
  "信義安和", "台北101/世貿", "市政府", "象山",
  "中山國小", "雙連", "行天宮", "中山",
];

const HOME_AI_QUICK_LINKS = [
  { label: "信義區想吃火鍋", href: "/ai" },
  { label: "大安區美式漢堡", href: "/ai" },
  { label: "明天 19:00 訂 2 人", href: "/ai" },
  { label: "有空位通知的熱門店", href: "/notifications" },
];

const PRODUCT_LOOPS = [
  {
    title: "AI 推薦",
    body: "Agent 依照類別、區域、評論語意做 curated recommendation，不再只是關鍵字搜尋。",
    href: "/ai",
    cta: "開始問 AI",
    icon: Bot,
  },
  {
    title: "真實訂位",
    body: "同一份 slot inventory 支援 AI Agent、商家後台與使用者訂位，避免假裝有位。",
    href: "/shops",
    cta: "查看可訂店家",
    icon: CalendarCheck,
  },
  {
    title: "空位通知",
    body: "額滿時段可建立 watch；釋出容量後站內 toast 主動提醒，不必自己回來刷新。",
    href: "/notifications",
    cta: "管理通知",
    icon: Bell,
  },
  {
    title: "收藏餐廳",
    body: "收藏會寫入使用者資料，未來可接個人化推薦，不是 localStorage 假 UI。",
    href: "/favorites",
    cta: "看收藏",
    icon: Heart,
  },
];

function parseTags(raw?: string): string[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.map(String) : [];
  } catch {
    return [];
  }
}

function getDisplaySpend(shop: Shop, meta?: ShopAiMetadata | null) {
  const overview = getShopOverview(shop.id);
  if (overview?.price_overview) return `平均每人 ${overview.price_overview}`;
  if (meta?.pricePerPerson) return `價位：${meta.pricePerPerson}`;
  if (shop.avgPrice) return `NT$ ${shop.avgPrice}`;
  return null;
}

function prioritizeVisibleShops(shops: Shop[]) {
  return [...shops].sort((a, b) => {
    const aSeed = isLegacySeedShop(a.id) ? 1 : 0;
    const bSeed = isLegacySeedShop(b.id) ? 1 : 0;
    if (aSeed !== bSeed) return aSeed - bSeed;
    const aPhoto = getBestShopCardPhoto(a.id, a.images) ? 1 : 0;
    const bPhoto = getBestShopCardPhoto(b.id, b.images) ? 1 : 0;
    if (bPhoto !== aPhoto) return bPhoto - aPhoto;
    return (b.score ?? 0) - (a.score ?? 0);
  });
}

function hasUsablePhoto(shop: Shop) {
  return Boolean(getBestShopCardPhoto(shop.id, shop.images));
}

export default async function Home() {
  let categories: Category[] = [];
  let aiOk = false;
  let stationShops: { data: Shop[] }[] = [];
  let totalShops = 0;
  let stationsWithShops: { name: string; shops: Shop[] }[] = [];

  const [categoriesRes, shopCountRes, aiHealthRes] = await Promise.all([
    javaApi.listCategories().catch(() => ({ data: [] as Category[] })),
    javaApi.shopCount().catch(() => ({ data: 0 })),
    aiApi.health().catch(() => ({ status: "off" })),
  ]);

  categories = (categoriesRes.data ?? []) as Category[];
  totalShops = shopCountRes.data ?? 0;
  aiOk = aiHealthRes.status === "ok";

  stationShops = await Promise.all(
    HOT_STATIONS.map((station) =>
      javaApi.popularShopsByMrt(station).catch(() => ({ data: [] as Shop[] })),
    ),
  );

  stationsWithShops = HOT_STATIONS
    .map((name, idx) => ({
      name,
      shops: (stationShops[idx]?.data ?? []).filter((shop) => !isLegacySeedShop(shop.id)),
    }))
    .filter((s) => s.shops.length > 0)
    .sort((a, b) => b.shops.length - a.shops.length);

  const featuredShops = stationsWithShops.flatMap((station) => station.shops.slice(0, 5));
  const featuredShopIds = Array.from(new Set(featuredShops.map((shop) => shop.id)));

  const [metadataEntries, hotSeatEntries] = await Promise.all([
    Promise.all(
      featuredShopIds.map(async (shopId) => {
        const res = await javaApi.shopAiMetadata(shopId).catch(() => ({ data: null as ShopAiMetadata | null }));
        return [shopId, res.data] as const;
      }),
    ),
    Promise.all(
      featuredShopIds.map(async (shopId) => {
        const res = await javaApi.hotSeatVouchers(shopId).catch(() => ({ data: [] as { id: number }[] }));
        return [shopId, res.data?.length ?? 0] as const;
      }),
    ),
  ]);

  const metadataMap = new Map<number, ShopAiMetadata | null>(metadataEntries);
  const hotSeatMap = new Map<number, number>(hotSeatEntries);

  return (
    <main className="bg-[#f6f1e8]">
      <section className="relative overflow-hidden border-b border-black/10">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_10%,rgba(20,120,80,0.18),transparent_34%),radial-gradient(circle_at_82%_18%,rgba(184,143,72,0.22),transparent_28%),linear-gradient(135deg,#f8f3ea_0%,#fffdf8_52%,#eef5ed_100%)]" />
        <div className="relative mx-auto grid min-h-[680px] max-w-7xl gap-10 px-4 py-14 md:grid-cols-[1.05fr_0.95fr] md:px-8 md:py-20">
          <div className="flex flex-col justify-center">
            <div className="mb-6 inline-flex w-fit items-center gap-2 rounded-full border border-emerald-200 bg-white/70 px-4 py-2 text-xs font-black uppercase tracking-[0.28em] text-emerald-800 shadow-sm">
              <Sparkles className="h-4 w-4" />
              ByteBites AI Dining Agent
            </div>
            <h1 className="max-w-3xl text-5xl font-black leading-[0.95] tracking-tight text-[#171512] md:text-7xl">
              不只推薦餐廳，
              <span className="block text-emerald-800">直接幫你完成訂位。</span>
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-8 text-zinc-600">
              對標 inline 的餐廳探索體驗，但把 AI Agent、真實 slot inventory、訂金付款、空位通知與收藏回訪串成同一條產品路徑。
            </p>

            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/ai">
                <Button size="lg" className="rounded-full bg-emerald-800 px-6 hover:bg-emerald-900">
                  問 AI 找餐廳
                </Button>
              </Link>
              <Link href="/shops">
                <Button size="lg" variant="outline" className="rounded-full border-black/15 bg-white/75 px-6">
                  探索全部餐廳
                </Button>
              </Link>
            </div>

            <div className="mt-7 grid max-w-2xl grid-cols-2 gap-3 md:grid-cols-4">
              {[
                ["TTFT", "908ms"],
                ["ABSA F1", "0.955"],
                ["DB shops", totalShops || "—"],
                ["AI", aiOk ? "ONLINE" : "OFFLINE"],
              ].map(([label, value]) => (
                <div key={label} className="rounded-2xl border border-black/10 bg-white/65 p-4 shadow-sm backdrop-blur">
                  <p className="text-xs font-bold uppercase tracking-[0.18em] text-zinc-400">{label}</p>
                  <p className="mt-1 font-mono text-2xl font-black text-[#171512]">{value}</p>
                </div>
              ))}
            </div>

            <div className="mt-6 flex flex-wrap gap-2">
              {HOME_AI_QUICK_LINKS.map((item) => (
                <Link key={item.label} href={item.href}>
                  <span className="inline-flex rounded-full border border-emerald-200 bg-white/70 px-3 py-1.5 text-xs font-bold text-emerald-800 transition hover:bg-emerald-50">
                    {item.label}
                  </span>
                </Link>
              ))}
            </div>
          </div>

          <div className="flex items-center">
            <div className="w-full overflow-hidden rounded-[2rem] border border-black/10 bg-[#111b16] p-4 shadow-2xl shadow-emerald-950/20">
              <div className="rounded-[1.5rem] bg-[#fdfbf5] p-4 md:p-5">
                <div className="flex items-center justify-between border-b border-black/10 pb-4">
                  <div>
                    <p className="text-xs font-black uppercase tracking-[0.24em] text-emerald-800">Live demo flow</p>
                    <p className="mt-1 text-lg font-black">信義區火鍋 · 明天 19:00 · 2 人</p>
                  </div>
                  <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-black text-emerald-800">
                    PAID
                  </span>
                </div>

                <div className="mt-5 space-y-3">
                  <div className="ml-auto max-w-[78%] rounded-2xl bg-emerald-800 px-4 py-3 text-sm font-bold text-white">
                    幫我訂辛殿麻辣鍋明天晚上 7 點 2 人
                  </div>
                  <div className="max-w-[86%] rounded-2xl bg-zinc-100 px-4 py-3 text-sm leading-6 text-zinc-700">
                    訂位已保留，請完成訂金付款。系統會先檢查店家容量，付款完成才正式成立。
                  </div>
                  <div className="rounded-3xl border border-emerald-200 bg-emerald-50 p-4">
                    <div className="flex items-center gap-2 text-emerald-900">
                      <CalendarCheck className="h-5 w-5" />
                      <p className="font-black">訂位 + 訂金完成</p>
                    </div>
                    <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
                      <div>
                        <p className="text-xs text-zinc-500">店家</p>
                        <p className="font-black">辛殿麻辣鍋｜信義店</p>
                      </div>
                      <div>
                        <p className="text-xs text-zinc-500">時間</p>
                        <p className="font-black">明天 19:00</p>
                      </div>
                      <div>
                        <p className="text-xs text-zinc-500">人數</p>
                        <p className="font-black">2 人</p>
                      </div>
                      <div>
                        <p className="text-xs text-zinc-500">訂金</p>
                        <p className="font-black">NT$ 200</p>
                      </div>
                    </div>
                  </div>
                  <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                    若時段額滿，可建立空位通知；釋出後站內 toast 會主動提醒。
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-10 md:px-8">
        <div className="grid gap-4 md:grid-cols-4">
          {PRODUCT_LOOPS.map((item) => {
            const Icon = item.icon;
            return (
              <Link key={item.title} href={item.href} className="group">
                <article className="h-full rounded-3xl border border-black/10 bg-white p-5 shadow-sm transition hover:-translate-y-1 hover:shadow-xl">
                  <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-800">
                    <Icon className="h-5 w-5" />
                  </div>
                  <h2 className="mt-5 text-xl font-black">{item.title}</h2>
                  <p className="mt-2 min-h-[72px] text-sm leading-6 text-zinc-600">{item.body}</p>
                  <p className="mt-4 text-sm font-black text-emerald-800 group-hover:underline">{item.cta}</p>
                </article>
              </Link>
            );
          })}
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-12 md:px-8">
        <div className="rounded-[2rem] border border-black/10 bg-white p-5 shadow-sm md:p-8">
          <div className="mb-6 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.28em] text-emerald-800">Browse by category</p>
              <h2 className="mt-2 text-3xl font-black">{categories.length} 個餐廳分類</h2>
              <p className="mt-2 text-sm text-zinc-500">
                以訂位與聚餐決策最常見的餐廳型態來分，不把所有 tag 混成一個字串。
              </p>
            </div>
            <Link href="/shops" className="text-sm font-black text-emerald-800 hover:underline">
              查看完整篩選
            </Link>
          </div>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4">
            {categories.map((category) => {
              const { icon: Icon, gradient } = getCategoryStyle(category.slug);
              return (
                <Link key={category.id} href={`/shops?types=${category.id}`}>
                  <div
                    className={`relative flex h-32 flex-col justify-between overflow-hidden rounded-2xl border bg-gradient-to-br p-5 transition hover:-translate-y-0.5 hover:border-emerald-800/40 hover:shadow-sm ${gradient}`}
                  >
                    <Icon className="h-8 w-8 text-foreground/70" strokeWidth={1.5} />
                    <div>
                      <div className="font-semibold">{category.name}</div>
                      <div className="text-muted-foreground/70 font-mono mt-0.5 text-xs">
                        {category.slug}
                      </div>
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 pb-16 md:px-8">
        <div className="mb-6 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.28em] text-emerald-800">Popular near MRT</p>
            <h2 className="mt-2 text-3xl font-black">捷運站熱門</h2>
            <p className="mt-2 text-sm text-zinc-500">每站最多 5 家，可左右滑看完整名單。</p>
          </div>
          <div className="rounded-full border border-black/10 bg-white px-4 py-2 text-sm font-bold text-zinc-600">
            {stationsWithShops.length || "—"} 個熱門站點
          </div>
        </div>

        <div className="space-y-8">
          {stationsWithShops.map(({ name: station, shops }) => {
            const visibleStationShops = prioritizeVisibleShops(shops)
              .filter((shop) => hasUsablePhoto(shop))
              .slice(0, 5);

            if (visibleStationShops.length === 0) return null;
            return (
              <div key={station}>
                <div className="mb-3 flex items-baseline justify-between">
                  <h3 className="font-medium">
                    捷運<span className="text-primary">{station}</span>站
                  </h3>
                  <span className="text-muted-foreground font-mono text-xs">{visibleStationShops.length} 家</span>
                </div>
                <div className="flex gap-3 overflow-x-auto pb-2 snap-x snap-mandatory">
                  {visibleStationShops.map((shop) => {
                    const style = getStyleByTypeId(shop.typeId);
                    const Icon = style.icon;
                    const fallbackImage = shop.images?.startsWith("http")
                      ? shop.images
                      : null;
                    const coverPhoto = proxyImageUrl(
                      getBestShopCardPhoto(shop.id, fallbackImage),
                    );
                    const displaySpend = getDisplaySpend(shop, metadataMap.get(shop.id));
                    const bookingDifficulty = metadataMap.get(shop.id)?.bookingDifficulty;
                    return (
                      <Link key={shop.id} href={`/shops/${shop.id}`} className="min-w-[280px] max-w-[280px] snap-start shrink-0">
                        <div className="overflow-hidden rounded-2xl border bg-white transition hover:-translate-y-0.5 hover:border-emerald-800/40 hover:shadow-md">
                          <div className={`relative flex aspect-[4/3] items-center justify-center overflow-hidden bg-gradient-to-br ${style.gradient}`}>
                            {coverPhoto ? (
                              <>
                                <img
                                  src={coverPhoto}
                                  alt={`${shop.name}-cover`}
                                  className="h-full w-full object-cover"
                                  loading="lazy"
                                />
                                <div className="absolute inset-0 bg-gradient-to-t from-black/45 via-black/10 to-transparent" />
                              </>
                            ) : (
                              <Icon className="h-7 w-7 text-foreground/40" strokeWidth={1.5} />
                            )}
                          </div>
                          <div className="p-3">
                            <div className="flex items-start justify-between gap-2">
                              <h4 className="text-sm leading-tight font-medium">{shop.name}</h4>
                              {shop.score ? (
                                <span className="bg-foreground text-background font-mono shrink-0 rounded px-1.5 py-0.5 text-xs">
                                  {(shop.score / 10).toFixed(1)}
                                </span>
                              ) : null}
                            </div>
                            {hotSeatMap.get(shop.id) ? (
                              <div className="mt-2 rounded-md border border-amber-200 bg-amber-50 px-2 py-1">
                                <div className="text-[11px] font-medium text-amber-800">
                                  Hot Seat {hotSeatMap.get(shop.id)} 案
                                </div>
                              </div>
                            ) : null}
                            {displaySpend ? (
                              <div className="text-muted-foreground mt-1 text-xs">
                                {displaySpend}
                              </div>
                            ) : null}
                            {bookingDifficulty && bookingDifficulty !== "未提及" ? (
                              <div className="mt-1 text-xs text-foreground/80">
                                {bookingDifficulty}
                              </div>
                            ) : null}
                            {metadataMap.get(shop.id)?.atmosphereTags ? (
                              <div className="mt-2 flex flex-wrap gap-1">
                                {parseTags(metadataMap.get(shop.id)?.atmosphereTags)
                                  .slice(0, 2)
                                  .map((tag: string) => (
                                    <span
                                      key={`${shop.id}-${tag}`}
                                      className="rounded-full bg-muted px-2 py-0.5 text-[10px] text-foreground/80"
                                    >
                                      {tag}
                                    </span>
                                  ))}
                              </div>
                            ) : null}
                          </div>
                        </div>
                      </Link>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </section>
    </main>
  );
}
