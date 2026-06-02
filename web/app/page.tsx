import Link from "next/link";
import { ArrowRight, Bot, Search, Sparkles } from "lucide-react";
import { javaApi, type Category, type Shop, type ShopAiMetadata } from "@/lib/api";
import { getCategoryStyle, getStyleByTypeId } from "@/lib/categoryStyle";
import { isLegacySeedShop } from "@/lib/legacySeedShops";
import { proxyImageUrl } from "@/lib/photoProxy";
import { getBestShopCardPhoto, getShopOverview } from "@/lib/shopPhotoManifest";

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

const AI_PROMPTS = ["信義區想吃火鍋", "今晚有位的約會餐廳", "大安區美式漢堡", "幫我訂明晚 7 點 2 人"];

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

function sortVisibleShops(shops: Shop[]) {
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

function getUniqueFeaturedShops(stationsWithShops: { name: string; shops: Shop[] }[]) {
  const seen = new Set<number>();
  const result: { station: string; shop: Shop }[] = [];

  for (const station of stationsWithShops) {
    for (const shop of sortVisibleShops(station.shops)) {
      if (seen.has(shop.id)) continue;
      if (!getBestShopCardPhoto(shop.id, shop.images)) continue;
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
        <p className="text-xs font-black tracking-[0.18em] text-[#b59a58]">{kicker}</p>
        <h2 className="mt-2 text-4xl font-black tracking-[-0.06em] text-[#191713] md:text-5xl">{title}</h2>
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

  return (
    <Link href={`/shops/${shop.id}`} className="group block h-full">
      <article className="flex h-full flex-col overflow-hidden rounded-[1.35rem] border border-[#ddd6c8] bg-[#fbf8f1] shadow-sm transition group-hover:-translate-y-0.5 group-hover:shadow-xl">
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
                <span key={`${shop.id}-${tag}`} className="rounded-full bg-black/65 px-2.5 py-1 text-xs font-black text-white">
                  {tag}
                </span>
              ))}
            </div>
          ) : null}
        </div>
        <div className="flex flex-1 flex-col p-5">
          <h3 className={`${compact ? "text-xl" : "text-2xl"} line-clamp-2 font-black tracking-[-0.04em]`}>
            {shop.name}
          </h3>
          <p className="mt-2 text-sm text-zinc-500">
            {style.label} · {shop.district ?? shop.area ?? item.station}
          </p>
          <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1 text-sm text-zinc-500">
            {shop.score ? <span className="font-black text-[#b59a58]">★ {shop.score.toFixed(1)}</span> : null}
            {shop.comments ? <span>{shop.comments.toLocaleString()} 則評論</span> : null}
            {shop.mrtStation ? <span>{shop.mrtStation}</span> : null}
          </div>
          <p className={`${compact ? "line-clamp-2" : "line-clamp-3"} mt-4 text-sm leading-6 text-zinc-600`}>
            {summary}
          </p>
          <div className="mt-auto flex items-center justify-between border-t border-[#e2dacb] pt-4 text-sm">
            <span className="font-medium text-zinc-500">{spend}</span>
            <span className="font-black text-[#191713]">查看時段</span>
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
            const shops = sortVisibleShops(row.shops).slice(0, 5);
            if (!shops.length) return null;

            return (
              <div key={row.name}>
                <div className="mb-4 flex items-center justify-between">
                  <div>
                    <p className="text-xs font-black tracking-[0.14em] text-[#b59a58]">MRT</p>
                    <h3 className="text-3xl font-black tracking-[-0.04em]">{row.name}</h3>
                  </div>
                  <Link
                    href={`/shops?mrt=${encodeURIComponent(row.name)}`}
                    className="rounded-full border border-[#ded7c9] px-4 py-2 text-sm font-black text-zinc-600 hover:bg-white"
                  >
                    查看站點
                  </Link>
                </div>
                <div className="flex gap-5 overflow-x-auto pb-2">
                  {shops.map((shop) => (
                    <div key={shop.id} className="min-w-[282px] max-w-[282px]">
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

export default async function Home() {
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
      <section className="border-b border-[#ded7c9] px-6 py-14 md:px-12 md:py-20">
        <div className="mx-auto grid max-w-7xl gap-10 lg:grid-cols-[0.9fr_1fr] lg:items-center">
          <div>
            <p className="text-sm font-black tracking-[0.16em] text-[#b59a58]">獨家桌位，僅此一處</p>
            <h1 className="mt-5 text-6xl font-black leading-[0.92] tracking-[-0.08em] md:text-8xl">
              餐飲體驗
              <span className="block text-[#b59a58]">臻於極致</span>
            </h1>
            <p className="mt-7 max-w-xl text-lg leading-8 text-zinc-600">
              ByteBites 連接餐廳探索、AI 推薦、空位通知與訂金付款。這裡不列出所有座位，只挑真正值得你花時間看的那一席。
            </p>
          </div>

          <div className="rounded-[2rem] border border-[#d9d1c1] bg-[#eee8dc] p-7 md:p-9">
            <div className="flex items-start gap-4">
              <Sparkles className="mt-1 h-8 w-8 fill-[#1c1914] text-[#1c1914]" />
              <div>
                <h2 className="text-3xl font-black tracking-[-0.05em] md:text-4xl">今晚想去哪？</h2>
                <p className="mt-2 text-zinc-600">用自然語言找最適合的一間</p>
              </div>
            </div>
            <Link
              href="/ai"
              className="mt-8 flex items-center gap-3 rounded-2xl border border-[#d9d1c1] bg-[#faf7ef] px-5 py-5 text-left text-zinc-500 transition hover:bg-white"
            >
              <Search className="h-5 w-5" />
              <span className="flex-1 text-sm font-black md:text-base">找餐廳、查空位、直接訂位</span>
              <Bot className="h-5 w-5 text-[#b59a58]" />
            </Link>
            <div className="mt-5 flex flex-wrap gap-3">
              {AI_PROMPTS.map((prompt) => (
                <Link key={prompt} href={`/ai?q=${encodeURIComponent(prompt)}`}>
                  <span className="inline-flex rounded-xl bg-[#e3d9c5] px-4 py-3 text-sm font-black text-zinc-600 transition hover:bg-[#d9c9ad]">
                    {prompt}
                  </span>
                </Link>
              ))}
            </div>
            <div className="mt-8 border-t border-[#d9d1c1] pt-6">
              <p className="font-mono text-4xl font-black">{totalShops || "—"}</p>
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
