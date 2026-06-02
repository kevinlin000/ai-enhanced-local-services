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

const AI_PROMPTS = [
  "附近好吃",
  "今晚有位",
  "一人燒肉",
  "Omakase 推薦",
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

function getUniqueFeaturedShops(stationsWithShops: { name: string; shops: Shop[] }[]) {
  const seen = new Set<number>();
  const result: { station: string; shop: Shop }[] = [];

  for (const station of stationsWithShops) {
    for (const shop of prioritizeVisibleShops(station.shops)) {
      if (seen.has(shop.id)) continue;
      if (!getBestShopCardPhoto(shop.id, shop.images)) continue;
      seen.add(shop.id);
      result.push({ station: station.name, shop });
      if (result.length >= 18) return result;
    }
  }

  return result;
}

function CategoryRail({ categories }: { categories: Category[] }) {
  return (
    <section className="border-b border-[#ded7c9] px-8 py-12 md:px-16">
      <div className="mx-auto max-w-7xl">
        <p className="text-sm font-black tracking-[0.14em] text-[#b59a58]">探索不同料理的餐廳</p>
        <div className="mt-8 flex gap-10 overflow-x-auto pb-3">
          {categories.slice(0, 12).map((category) => {
            const { icon: Icon } = getCategoryStyle(category.slug);
            return (
              <Link
                key={category.id}
                href={`/shops?types=${category.id}`}
                className="group flex min-w-[112px] flex-col items-center gap-4"
              >
                <div className="flex h-24 w-24 items-center justify-center rounded-[1.75rem] border border-[#ded7c9] bg-[#f1eadc] transition group-hover:-translate-y-1 group-hover:bg-white group-hover:shadow-md">
                  <Icon className="h-11 w-11 text-[#6f695d]" strokeWidth={1.25} />
                </div>
                <span className="text-center text-base font-black">{category.name}</span>
              </Link>
            );
          })}
        </div>
      </div>
    </section>
  );
}

function EditorialCard({
  item,
  metadata,
  size = "normal",
  badge,
}: {
  item: { station: string; shop: Shop };
  metadata?: ShopAiMetadata | null;
  size?: "hero" | "normal";
  badge?: string;
}) {
  const shop = item.shop;
  const style = getStyleByTypeId(shop.typeId);
  const photo = proxyImageUrl(getBestShopCardPhoto(shop.id, shop.images));
  const spend = getDisplaySpend(shop, metadata);
  const summary = getSummary(shop, metadata);
  const tags = parseTags(metadata?.atmosphereTags).slice(0, 2);

  return (
    <Link href={`/shops/${shop.id}`} className="group block h-full">
      <article className="flex h-full flex-col overflow-hidden border border-[#d9d1c1] bg-[#eee9df] transition group-hover:-translate-y-1 group-hover:shadow-xl">
        <div className={`relative overflow-hidden bg-[#e4ddcf] ${size === "hero" ? "aspect-[1.72/1]" : "aspect-[1.55/1]"}`}>
          {photo ? (
            <img src={photo} alt={shop.name} className="h-full w-full object-cover transition duration-500 group-hover:scale-[1.03]" loading="lazy" />
          ) : null}
          <div className="absolute left-5 top-5 flex gap-2">
            {badge ? (
              <span className="rounded bg-[#951f1f] px-3 py-1 text-xs font-black text-white shadow-sm">
                {badge}
              </span>
            ) : null}
            {tags.map((tag) => (
              <span key={`${shop.id}-${tag}`} className="hidden rounded bg-black/70 px-3 py-1 text-xs font-black text-white shadow-sm md:inline-flex">
                {tag}
              </span>
            ))}
          </div>
        </div>
        <div className={`flex flex-1 flex-col ${size === "hero" ? "p-7" : "p-5"}`}>
          <h3 className={`line-clamp-2 font-serif tracking-[-0.04em] ${size === "hero" ? "text-4xl" : "text-3xl"}`}>
            {shop.name}
          </h3>
          <p className="mt-2 text-sm text-zinc-500">
            {style.label} · {shop.district ?? shop.area ?? item.station}
          </p>
          <p className={`mt-4 line-clamp-3 leading-7 text-zinc-600 ${size === "hero" ? "text-base" : "text-sm"}`}>
            {summary}
          </p>
          <div className="mt-auto flex items-center justify-between border-t border-[#d8d0bf] pt-5 text-sm">
            <span className="font-medium text-zinc-500">{spend}</span>
            <span className="font-black text-[#b59a58]">查看時段</span>
          </div>
        </div>
      </article>
    </Link>
  );
}

function SectionHeader({
  kicker,
  title,
  href,
  cta,
}: {
  kicker: string;
  title: string;
  href?: string;
  cta?: string;
}) {
  return (
    <div className="mb-7 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
      <div>
        <p className="text-sm font-black tracking-[0.14em] text-[#b59a58]">{kicker}</p>
        <h2 className="mt-2 font-serif text-5xl tracking-[-0.06em] text-[#2a251f]">{title}</h2>
      </div>
      {href && cta ? (
        <Link href={href} className="inline-flex w-fit items-center gap-2 rounded-xl border border-[#d9d1c1] bg-[#f6f1e8] px-5 py-3 text-sm font-black text-[#7f6b35] hover:bg-white">
          {cta}
          <ArrowRight className="h-4 w-4" />
        </Link>
      ) : null}
    </div>
  );
}

function CardRow({
  items,
  metadataMap,
  badge,
}: {
  items: { station: string; shop: Shop }[];
  metadataMap: Map<number, ShopAiMetadata | null>;
  badge?: string;
}) {
  if (!items.length) return null;
  return (
    <div className="grid gap-6 md:grid-cols-3">
      {items.map((item) => (
        <EditorialCard key={item.shop.id} item={item} metadata={metadataMap.get(item.shop.id)} badge={badge} />
      ))}
    </div>
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
    HOT_STATIONS.map((station) =>
      javaApi.popularShopsByMrt(station).catch(() => ({ data: [] as Shop[] })),
    ),
  );

  const stationsWithShops = HOT_STATIONS
    .map((name, idx) => ({
      name,
      shops: (stationShops[idx]?.data ?? []).filter((shop) => !isLegacySeedShop(shop.id)),
    }))
    .filter((s) => s.shops.length > 0)
    .sort((a, b) => b.shops.length - a.shops.length);

  const featuredItems = getUniqueFeaturedShops(stationsWithShops);
  const metadataEntries = await Promise.all(
    featuredItems.map(async ({ shop }) => {
      const res = await javaApi.shopAiMetadata(shop.id).catch(() => ({ data: null as ShopAiMetadata | null }));
      return [shop.id, res.data] as const;
    }),
  );
  const metadataMap = new Map<number, ShopAiMetadata | null>(metadataEntries);

  const spotlight = featuredItems[0];
  const editorsPicks = featuredItems.slice(1, 5);
  const topicShops = featuredItems.slice(5, 8);
  const hotShops = featuredItems.slice(8, 11);
  const moreShops = featuredItems.slice(11, 14);

  return (
    <main className="min-h-screen bg-[#f6f1e8] text-[#27231d]">
      <section className="border-b border-[#ded7c9]">
        <div className="mx-auto grid min-h-[620px] max-w-7xl gap-14 px-8 py-16 md:grid-cols-[0.95fr_1.05fr] md:px-16 md:py-24">
          <div className="flex flex-col justify-center">
            <p className="text-sm font-black tracking-[0.14em] text-[#b59a58]">獨家桌位，僅此一處</p>
            <h1 className="mt-6 font-serif text-7xl leading-[0.86] tracking-[-0.08em] md:text-8xl">
              餐飲體驗
              <span className="block text-[#b59a58]">臻於極致</span>
            </h1>
            <p className="mt-8 max-w-lg text-lg leading-9 text-zinc-600">
              ByteBites 連接餐廳探索、AI 推薦、空位通知與訂金付款。這裡不列出所有座位，只挑真正值得你花時間看的那一席。
            </p>
          </div>

          <div className="flex items-center">
            <div className="w-full rounded-[2rem] border border-[#d9d1c1] bg-[#eee8dc] p-8">
              <div className="flex items-start gap-4">
                <Sparkles className="mt-1 h-8 w-8 fill-[#171512] text-[#171512]" />
                <div>
                  <h2 className="text-4xl font-black tracking-[-0.04em]">今晚想去哪？</h2>
                  <p className="mt-2 text-zinc-600">告訴 ByteBites AI，幫你找到最適合的一間</p>
                </div>
              </div>
              <Link
                href="/ai"
                className="mt-8 flex items-center gap-3 rounded-2xl border border-[#d9d1c1] bg-[#faf7ef] px-5 py-5 text-left text-zinc-500 transition hover:bg-white"
              >
                <Search className="h-5 w-5" />
                <span className="flex-1 text-base font-black">登入後找餐廳、查空位、直接訂位</span>
                <Bot className="h-5 w-5 text-[#b59a58]" />
              </Link>
              <div className="mt-6 flex flex-wrap gap-3">
                {AI_PROMPTS.map((prompt) => (
                  <Link key={prompt} href={`/ai?q=${encodeURIComponent(prompt)}`}>
                    <span className="inline-flex rounded-xl bg-[#e3d9c5] px-4 py-3 text-sm font-black text-zinc-600 transition hover:bg-[#d9c9ad]">
                      {prompt}
                    </span>
                  </Link>
                ))}
              </div>
              <div className="mt-8 border-t border-[#d9d1c1] pt-7">
                <p className="font-mono text-4xl font-black">{totalShops || "—"}</p>
                <p className="mt-1 text-sm font-medium text-zinc-500">間餐廳資料，持續擴充中</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <CategoryRail categories={categories} />

      {spotlight ? (
        <section className="px-8 py-16 md:px-16">
          <div className="mx-auto max-w-7xl">
            <SectionHeader kicker="主編精選" title="值得優先看的餐廳" href="/shops" cta="查看所有精選餐廳" />
            <div className="grid gap-6 lg:grid-cols-[1.25fr_1fr]">
              <EditorialCard item={spotlight} metadata={metadataMap.get(spotlight.shop.id)} size="hero" badge="精選" />
              <div className="grid gap-6 md:grid-cols-2">
                {editorsPicks.map((item) => (
                  <EditorialCard key={item.shop.id} item={item} metadata={metadataMap.get(item.shop.id)} badge="推薦" />
                ))}
              </div>
            </div>
          </div>
        </section>
      ) : null}

      <section className="bg-[#ece7dd] px-8 py-14 md:px-16">
        <div className="mx-auto max-w-7xl">
          <p className="text-sm font-black tracking-[0.14em] text-[#b59a58]">最新消息</p>
          <h2 className="mt-3 font-serif text-5xl tracking-[-0.06em]">ByteBites News</h2>
          <div className="mt-8 grid gap-5 md:grid-cols-3">
            {[
              ["信義火鍋推薦", "辛殿、海底撈與刁民等熱門選擇，適合聚餐與宵夜。"],
              ["訂金付款上線", "可保留座位後完成 TapPay sandbox 訂金付款。"],
              ["空位釋出通知", "額滿時段有位時，系統會主動提醒你回來訂位。"],
            ].map(([title, body]) => (
              <Link key={title} href="/ai" className="grid grid-cols-[112px_1fr_auto] items-center gap-4 bg-[#f8f5ee] p-4 transition hover:bg-white">
                <div className="h-24 bg-[#d9c9ad]" />
                <div>
                  <p className="text-xs font-black tracking-[0.12em] text-[#b59a58]">NEWSROOM</p>
                  <h3 className="mt-1 text-lg font-black">{title}</h3>
                  <p className="mt-1 line-clamp-1 text-sm text-zinc-500">{body}</p>
                </div>
                <ArrowRight className="h-5 w-5 text-zinc-500" />
              </Link>
            ))}
          </div>
        </div>
      </section>

      <section className="px-8 py-16 md:px-16">
        <div className="mx-auto max-w-7xl">
          <SectionHeader kicker="快速竄紅" title="本週話題餐廳" href="/shops" cta="查看所有本週話題餐廳" />
          <CardRow items={topicShops} metadataMap={metadataMap} badge="熱門" />
        </div>
      </section>

      <section className="px-8 pb-16 md:px-16">
        <div className="mx-auto max-w-7xl">
          <SectionHeader kicker="眾所嚮往" title="熱門餐廳" href="/shops" cta="查看所有熱門餐廳" />
          <CardRow items={hotShops.length ? hotShops : editorsPicks.slice(0, 3)} metadataMap={metadataMap} badge="可訂" />
        </div>
      </section>

      <section className="px-8 pb-20 md:px-16">
        <div className="mx-auto max-w-7xl">
          <SectionHeader kicker="精選" title="你的口袋名單" />
          <div className="grid gap-6 border-t border-[#ded7c9] pt-8 md:grid-cols-[1fr_1fr]">
            <Link href="/favorites" className="rounded-[1.5rem] border border-[#d9d1c1] bg-[#eee8dc] p-7 transition hover:bg-white">
              <h3 className="text-2xl font-black">收藏餐廳</h3>
              <p className="mt-2 text-sm leading-6 text-zinc-500">把想吃、想訂、想等空位的餐廳集中管理。</p>
            </Link>
            <Link href="/notifications" className="rounded-[1.5rem] border border-[#d9d1c1] bg-[#eee8dc] p-7 transition hover:bg-white">
              <h3 className="text-2xl font-black">空位釋出通知</h3>
              <p className="mt-2 text-sm leading-6 text-zinc-500">額滿時段有位時主動提醒，不需要反覆刷新。</p>
            </Link>
          </div>
          {moreShops.length ? (
            <div className="mt-12">
              <SectionHeader kicker="更多選擇" title="繼續探索" href="/shops" cta="查看全部餐廳" />
              <CardRow items={moreShops} metadataMap={metadataMap} />
            </div>
          ) : null}
        </div>
      </section>
    </main>
  );
}
