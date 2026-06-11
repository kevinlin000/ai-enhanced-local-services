import Link from "next/link";
import { AlertCircle, ArrowRight, Bot, Search, Sparkles } from "lucide-react";
import { javaApi, type Category, type Shop, type ShopAiMetadata } from "@/lib/api";
import { getCategoryStyle, getStyleByTypeId } from "@/lib/categoryStyle";
import { isLegacySeedShop } from "@/lib/legacySeedShops";
import { proxyImageUrl } from "@/lib/photoProxy";
import { getBestShopCardPhoto, getShopDataQualityScore, getShopOverview, isCuratedShopData } from "@/lib/shopPhotoManifest";

const HOT_STATIONS = [
  "信義安和",
  "台北101/世貿",
  "市政府",
  "象山",
  "中山國小",
  "雙連",
  "行天宮",
  "中山",
];

const AI_PROMPTS = ["中山區 4 人台菜包廂", "明晚 7 點可訂火鍋", "大安區適合聊天聚餐", "訂位後需要停車提醒"];

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
  if (overview?.price_overview) return overview.price_overview;
  if (meta?.pricePerPerson && meta.pricePerPerson !== "未提及") return meta.pricePerPerson;
  if (shop.avgPrice) return `NT$ ${shop.avgPrice}`;
  return "價格未提及";
}

function getSummary(shop: Shop, meta?: ShopAiMetadata | null) {
  if (meta?.aiSummary) return meta.aiSummary;
  if (shop.address) return `${shop.address}。查看餐廳資訊、評論與可訂時段。`;
  return "查看餐廳資訊、評論與可訂時段。";
}

function formatRating(score?: number) {
  if (!score) return null;
  const normalized = score > 10 ? score / 10 : score;
  return normalized.toFixed(1);
}

function sortVisibleShops(shops: Shop[]) {
  return [...shops].sort((a, b) => {
    const aSeed = isLegacySeedShop(a.id) ? 1 : 0;
    const bSeed = isLegacySeedShop(b.id) ? 1 : 0;
    if (aSeed !== bSeed) return aSeed - bSeed;

    const aQuality = getShopDataQualityScore(a.id, a.images, a.comments);
    const bQuality = getShopDataQualityScore(b.id, b.images, b.comments);
    if (bQuality !== aQuality) return bQuality - aQuality;

    return (b.score ?? 0) - (a.score ?? 0);
  });
}

function curatedFirst(shops: Shop[]) {
  const sorted = sortVisibleShops(shops);
  const curated = sorted.filter((shop) => isCuratedShopData(shop.id, shop.images));
  return curated.length ? curated : sorted.filter((shop) => getBestShopCardPhoto(shop.id, shop.images));
}

function getUniqueFeaturedShops(stationsWithShops: { name: string; shops: Shop[] }[]) {
  const seen = new Set<number>();
  const result: { station: string; shop: Shop }[] = [];
  const sortedByStation = stationsWithShops.map((station) => ({
    name: station.name,
    shops: sortVisibleShops(station.shops),
  }));

  // First pass: one representative per MRT area, so the homepage does not look
  // like a single station duplicated across every editorial card.
  for (const station of sortedByStation) {
    const shop = curatedFirst(station.shops).find((candidate) => !seen.has(candidate.id));
    if (!shop) continue;
    seen.add(shop.id);
    result.push({ station: station.name, shop });
    if (result.length >= 8) return result;
  }

  for (const station of sortedByStation) {
    for (const shop of curatedFirst(station.shops)) {
      if (seen.has(shop.id)) continue;
      seen.add(shop.id);
      result.push({ station: station.name, shop });
      if (result.length >= 16) return result;
    }
  }

  return result;
}

function SectionHeader({
  kicker,
  title,
  description,
  href,
  cta,
}: {
  kicker: string;
  title: string;
  description?: string;
  href?: string;
  cta?: string;
}) {
  return (
    <div className="mb-8 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
      <div>
        <p className="text-xs font-black tracking-normal text-[#b59a58]">{kicker}</p>
        <h2 className="mt-2 text-4xl font-black tracking-normal text-[#191713] md:text-5xl">{title}</h2>
        {description ? <p className="mt-3 max-w-2xl text-sm leading-6 text-zinc-500 md:text-base">{description}</p> : null}
      </div>
      {href && cta ? (
        <Link
          href={href}
          className="inline-flex w-fit items-center gap-2 rounded-full border border-[#d9d1c1] bg-[#f8f5ee] px-5 py-3 text-sm font-black text-[#7b682f] transition hover:bg-white"
        >
          {cta}
          <ArrowRight className="h-4 w-4" />
        </Link>
      ) : null}
    </div>
  );
}

function CategoryRail({ categories }: { categories: Category[] }) {
  if (!categories.length) return null;

  return (
    <section className="border-b border-[#ded7c9] px-6 py-10 md:px-12">
      <div className="mx-auto max-w-7xl">
        <p className="text-sm font-black">探索不同料理的餐廳</p>
        <div className="mt-6 flex gap-8 overflow-x-auto pb-2">
          {categories.slice(0, 12).map((category) => {
            const { icon: Icon } = getCategoryStyle(category.slug);
            return (
              <Link
                key={category.id}
                href={`/shops?types=${category.id}`}
                className="group flex min-w-[96px] flex-col items-center gap-3 text-center"
              >
                <div className="flex h-24 w-24 items-center justify-center rounded-[1.75rem] border border-[#ded7c9] bg-[#f4efe6] transition group-hover:-translate-y-1 group-hover:bg-white group-hover:shadow-md">
                  <Icon className="h-10 w-10 text-[#2e2a24]" strokeWidth={1.35} />
                </div>
                <span className="text-sm font-black">{category.name}</span>
              </Link>
            );
          })}
        </div>
      </div>
    </section>
  );
}

function RestaurantCard({
  item,
  metadata,
  compact = false,
}: {
  item: { station: string; shop: Shop };
  metadata?: ShopAiMetadata | null;
  compact?: boolean;
}) {
  const shop = item.shop;
  const style = getStyleByTypeId(shop.typeId);
  const photo = proxyImageUrl(getBestShopCardPhoto(shop.id, shop.images));
  const spend = getDisplaySpend(shop, metadata);
  const summary = getSummary(shop, metadata);
  const tags = parseTags(metadata?.atmosphereTags).slice(0, 2);
  const rating = formatRating(shop.score);

  return (
    <Link href={`/shops/${shop.id}`} className="group block h-full">
      <article className="flex h-full flex-col overflow-hidden rounded-2xl border border-[#ddd6c8] bg-[#fbf8f1] shadow-sm transition group-hover:-translate-y-0.5 group-hover:shadow-md">
        <div className="relative aspect-[4/3] overflow-hidden bg-[#e5ded0]">
          {photo ? (
            <img
              src={photo}
              alt={shop.name}
              className="h-full w-full object-cover transition duration-500 group-hover:scale-[1.03]"
              loading="lazy"
            />
          ) : (
            <div className="flex h-full w-full items-center justify-center text-sm font-black text-zinc-400">
              ByteBites
            </div>
          )}
          {tags.length ? (
            <div className="absolute left-3 top-3 flex gap-2">
              {tags.map((tag) => (
                <span key={`${shop.id}-${tag}`} className="rounded-full bg-black/65 px-2.5 py-1 text-xs font-semibold text-white">
                  {tag}
                </span>
              ))}
            </div>
          ) : null}
        </div>
        <div className="flex flex-1 flex-col p-5">
          <h3 className={`${compact ? "text-xl" : "text-2xl"} line-clamp-2 font-semibold tracking-normal`}>
            {shop.name}
          </h3>
          <p className="mt-2 text-sm text-zinc-500">
            {style.label} · {shop.district ?? shop.area ?? item.station}
          </p>
          <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1 text-sm text-zinc-500">
            {rating ? <span className="font-semibold text-[#b59a58]">★ {rating}</span> : null}
            {shop.comments ? <span>{shop.comments.toLocaleString()} 則評論</span> : null}
            {shop.mrtStation ? <span>{shop.mrtStation}</span> : null}
          </div>
          <p className={`${compact ? "line-clamp-2" : "line-clamp-3"} mt-4 text-sm leading-6 text-zinc-600`}>
            {summary}
          </p>
          <div className="mt-auto flex items-center justify-between border-t border-[#e2dacb] pt-4 text-sm">
            <span className="font-medium text-zinc-500">{spend}</span>
            <span className="font-semibold text-[#191713]">查看時段</span>
          </div>
        </div>
      </article>
    </Link>
  );
}

function FeaturedGrid({
  items,
  metadataMap,
}: {
  items: { station: string; shop: Shop }[];
  metadataMap: Map<number, ShopAiMetadata | null>;
}) {
  if (!items.length) return null;

  return (
    <section className="px-6 py-14 md:px-12">
      <div className="mx-auto max-w-7xl">
        <SectionHeader
          kicker="主編精選"
          title="值得優先看的餐廳"
          description="以真實店家資料、評論摘要與可訂狀態做精選，不用假排行榜填版面。"
          href="/shops"
          cta="查看所有餐廳"
        />
        <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-4">
          {items.slice(0, 4).map((item) => (
            <RestaurantCard key={item.shop.id} item={item} metadata={metadataMap.get(item.shop.id)} />
          ))}
        </div>
      </div>
    </section>
  );
}

function MrtPopularSection({
  stationsWithShops,
  metadataMap,
}: {
  stationsWithShops: { name: string; shops: Shop[] }[];
  metadataMap: Map<number, ShopAiMetadata | null>;
}) {
  const rows = stationsWithShops.slice(0, 5);
  if (!rows.length) return null;

  return (
    <section className="border-t border-[#ded7c9] px-6 py-14 md:px-12">
      <div className="mx-auto max-w-7xl">
        <SectionHeader
          kicker="捷運站熱門"
          title="沿著捷運找好店"
          description="恢復原本最有 ByteBites 特色的捷運搜尋邏輯。每一列都是真實站點資料，不是靜態展示。"
          href="/shops"
          cta="探索全部餐廳"
        />
        <div className="space-y-10">
          {rows.map((row) => {
            const shops = curatedFirst(row.shops).slice(0, 4);
            if (!shops.length) return null;

            return (
              <div key={row.name}>
                <div className="mb-4 flex items-center justify-between">
                  <div>
                    <p className="text-xs font-black tracking-normal text-[#b59a58]">MRT</p>
                    <h3 className="text-3xl font-black tracking-normal">{row.name}</h3>
                  </div>
                  <Link
                    href={`/shops?mrt=${encodeURIComponent(row.name)}`}
                    className="rounded-full border border-[#ded7c9] px-4 py-2 text-sm font-black text-zinc-600 hover:bg-white"
                  >
                    查看站點
                  </Link>
                </div>
                <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
                  {shops.map((shop) => (
                    <div key={shop.id}>
                      <RestaurantCard item={{ station: row.name, shop }} metadata={metadataMap.get(shop.id)} compact />
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

function UtilityStrip() {
  return (
    <section className="px-6 pb-16 md:px-12">
      <div className="mx-auto grid max-w-7xl gap-4 md:grid-cols-3">
        {[
          ["與 AI 助手聊天", "用自然語言完成推薦、查空位、保留訂位。", "/ai"],
          ["空位釋出通知", "額滿時段建立 watch，有位時主動提醒。", "/notifications"],
          ["我的訂位", "管理待付款、已付款與已取消的訂位。", "/my-bookings"],
        ].map(([title, body, href]) => (
          <Link
            key={title}
            href={href}
            className="rounded-[1.5rem] border border-[#ddd6c8] bg-[#fbf8f1] p-6 shadow-sm transition hover:-translate-y-0.5 hover:shadow-lg"
          >
            <h3 className="text-xl font-black">{title}</h3>
            <p className="mt-2 text-sm leading-6 text-zinc-500">{body}</p>
          </Link>
        ))}
      </div>
    </section>
  );
}

export default async function Home({
  searchParams,
}: {
  searchParams?: Promise<{ login_failed?: string }>;
}) {
  const params = await searchParams;
  const loginFailed = params?.login_failed;

  const [categoriesRes, shopCountRes] = await Promise.all([
    javaApi.listCategories().catch(() => ({ data: [] as Category[] })),
    javaApi.shopCount().catch(() => ({ data: 0 })),
  ]);

  const categories = (categoriesRes.data ?? []) as Category[];
  const totalShops = shopCountRes.data ?? 0;

  const stationShops = await Promise.all(
    HOT_STATIONS.map((station) => javaApi.popularShopsByMrt(station).catch(() => ({ data: [] as Shop[] }))),
  );

  const stationsWithShops = HOT_STATIONS
    .map((name, idx) => ({
      name,
      shops: (stationShops[idx]?.data ?? []).filter((shop) => !isLegacySeedShop(shop.id)),
    }))
    .filter((station) => station.shops.length > 0)
    .sort((a, b) => b.shops.length - a.shops.length);

  const featuredItems = getUniqueFeaturedShops(stationsWithShops);
  const metadataShopIds = Array.from(
    new Set([
      ...featuredItems.slice(0, 8).map((item) => item.shop.id),
      ...stationsWithShops.flatMap((station) => sortVisibleShops(station.shops).slice(0, 3).map((shop) => shop.id)),
    ]),
  );

  const metadataEntries = await Promise.all(
    metadataShopIds.map(async (shopId) => {
      const res = await javaApi.shopAiMetadata(shopId).catch(() => ({ data: null as ShopAiMetadata | null }));
      return [shopId, res.data] as const;
    }),
  );
  const metadataMap = new Map<number, ShopAiMetadata | null>(metadataEntries);

  return (
    <main className="min-h-screen bg-[#f6f1e8] text-[#1c1914]">
      {loginFailed ? (
        <div className="border-b border-red-200 bg-red-50 px-6 py-3 text-sm font-bold text-red-900 md:px-12">
          <div className="mx-auto flex max-w-7xl items-center gap-2">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>LINE 登入失敗：{loginFailed}</span>
          </div>
        </div>
      ) : null}
      <section className="border-b border-[#ded7c9] px-6 py-12 md:px-12 md:py-16">
        <div className="mx-auto grid max-w-7xl gap-10 lg:grid-cols-[0.9fr_1fr] lg:items-center">
          <div>
            <p className="text-sm font-semibold tracking-normal text-[#b59a58]">AI 訂位決策平台</p>
            <h1 className="mt-5 text-5xl font-semibold leading-[1.02] tracking-normal md:text-7xl">
              從需求到入座
              <span className="block text-[#b59a58]">一次排好</span>
            </h1>
            <p className="mt-7 max-w-xl text-lg leading-8 text-zinc-600">
              ByteBites 把餐廳搜尋、AI 推薦、訂位付款、候補通知與停車提醒接在同一個流程。你說需求，系統負責縮小選項並完成後續安排。
            </p>
          </div>

          <div className="rounded-2xl border border-[#d9d1c1] bg-[#eee8dc] p-6 md:p-8">
            <div className="flex items-start gap-4">
              <Sparkles className="mt-1 h-8 w-8 fill-[#1c1914] text-[#1c1914]" />
              <div>
                <h2 className="text-3xl font-semibold tracking-normal md:text-4xl">輸入需求，直接安排</h2>
                <p className="mt-2 text-zinc-600">推薦、訂位、付款與通知同步處理</p>
              </div>
            </div>
            <Link
              href="/ai"
              className="mt-8 flex items-center gap-3 rounded-xl border border-[#d9d1c1] bg-[#faf7ef] px-5 py-4 text-left text-zinc-500 transition hover:bg-white"
            >
              <Search className="h-5 w-5" />
              <span className="flex-1 text-sm font-semibold md:text-base">描述人數、地點、料理與時間</span>
              <Bot className="h-5 w-5 text-[#b59a58]" />
            </Link>
            <div className="mt-5 flex flex-wrap gap-3">
              {AI_PROMPTS.map((prompt) => (
                <Link key={prompt} href={`/ai?q=${encodeURIComponent(prompt)}`}>
                  <span className="inline-flex rounded-lg bg-[#e3d9c5] px-4 py-2.5 text-sm font-semibold text-zinc-600 transition hover:bg-[#d9c9ad]">
                    {prompt}
                  </span>
                </Link>
              ))}
            </div>
            <div className="mt-8 border-t border-[#d9d1c1] pt-6">
              <p className="font-mono text-4xl font-semibold">{totalShops || "—"}</p>
              <p className="mt-1 text-sm font-medium text-zinc-500">間餐廳資料，持續擴充中</p>
            </div>
          </div>
        </div>
      </section>

      <CategoryRail categories={categories} />
      <FeaturedGrid items={featuredItems} metadataMap={metadataMap} />
      <MrtPopularSection stationsWithShops={stationsWithShops} metadataMap={metadataMap} />
      <UtilityStrip />
    </main>
  );
}
