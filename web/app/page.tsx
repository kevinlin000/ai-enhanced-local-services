import Link from "next/link";
import { ArrowRight, Bot, CalendarDays, Search, Sparkles } from "lucide-react";
import { aiApi, javaApi, type Category, type Shop, type ShopAiMetadata } from "@/lib/api";
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
  "信義區想吃火鍋",
  "今晚有位的約會餐廳",
  "大安區美式漢堡",
  "幫我訂明天晚上 7 點 2 人",
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

function getUniqueFeaturedShops(stationsWithShops: { name: string; shops: Shop[] }[]) {
  const seen = new Set<number>();
  const result: { station: string; shop: Shop }[] = [];

  for (const station of stationsWithShops) {
    for (const shop of prioritizeVisibleShops(station.shops)) {
      if (seen.has(shop.id)) continue;
      if (!getBestShopCardPhoto(shop.id, shop.images)) continue;
      seen.add(shop.id);
      result.push({ station: station.name, shop });
      if (result.length >= 8) return result;
    }
  }

  return result;
}

function CategoryRail({ categories }: { categories: Category[] }) {
  return (
    <section className="border-b border-black/10 bg-[#f6f1e8] px-6 py-10 md:px-12">
      <div className="mb-8 flex items-end justify-between gap-4">
        <div>
          <p className="text-xs font-black tracking-[0.22em] text-[#b89f61]">探索餐廳分類</p>
          <h2 className="mt-2 text-2xl font-black text-[#171512]">找一種今晚想吃的方向</h2>
        </div>
        <Link href="/shops" className="hidden items-center gap-2 text-sm font-black text-[#866f34] hover:underline md:flex">
          全部餐廳
          <ArrowRight className="h-4 w-4" />
        </Link>
      </div>

      <div className="flex gap-7 overflow-x-auto pb-2">
        {categories.slice(0, 12).map((category) => {
          const { icon: Icon, gradient } = getCategoryStyle(category.slug);
          return (
            <Link
              key={category.id}
              href={`/shops?types=${category.id}`}
              className="group flex min-w-[118px] flex-col items-center gap-3"
            >
              <div
                className={`flex h-24 w-24 items-center justify-center rounded-[2rem] border border-black/10 bg-gradient-to-br shadow-sm transition group-hover:-translate-y-1 group-hover:shadow-md ${gradient}`}
              >
                <Icon className="h-10 w-10 text-[#171512]/70" strokeWidth={1.4} />
              </div>
              <span className="text-center text-sm font-black text-[#171512]">{category.name}</span>
            </Link>
          );
        })}
      </div>
    </section>
  );
}

function FeaturedShopCard({
  item,
  metadata,
}: {
  item: { station: string; shop: Shop };
  metadata?: ShopAiMetadata | null;
}) {
  const shop = item.shop;
  const style = getStyleByTypeId(shop.typeId);
  const Icon = style.icon;
  const coverPhoto = proxyImageUrl(getBestShopCardPhoto(shop.id, shop.images));
  const spend = getDisplaySpend(shop, metadata);
  const tags = parseTags(metadata?.atmosphereTags).slice(0, 2);

  return (
    <Link href={`/shops/${shop.id}`} className="group block">
      <article className="overflow-hidden rounded-[1.75rem] border border-black/10 bg-white shadow-sm transition group-hover:-translate-y-1 group-hover:shadow-xl">
        <div className={`relative aspect-[4/3] overflow-hidden bg-gradient-to-br ${style.gradient}`}>
          {coverPhoto ? (
            <img src={coverPhoto} alt={`${shop.name} cover`} className="h-full w-full object-cover" loading="lazy" />
          ) : (
            <div className="flex h-full items-center justify-center">
              <Icon className="h-10 w-10 text-[#171512]/40" strokeWidth={1.4} />
            </div>
          )}
          <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/55 to-transparent p-4">
            <p className="text-xs font-black text-white/75">捷運 {item.station}</p>
            <h3 className="line-clamp-1 text-lg font-black text-white">{shop.name}</h3>
          </div>
        </div>

        <div className="space-y-3 p-4">
          <div className="flex items-center gap-2 text-sm text-zinc-600">
            {shop.score ? <span className="font-black text-[#b89f61]">★ {(shop.score / 10).toFixed(1)}</span> : null}
            {shop.comments ? <span>({shop.comments.toLocaleString()})</span> : null}
            {spend ? <span className="truncate">· {spend}</span> : null}
          </div>

          {metadata?.bookingDifficulty && metadata.bookingDifficulty !== "未提及" ? (
            <p className="line-clamp-2 text-sm leading-6 text-[#171512]">{metadata.bookingDifficulty}</p>
          ) : (
            <p className="line-clamp-2 text-sm leading-6 text-zinc-600">{shop.address ?? shop.district ?? "查看餐廳資訊與可訂時段"}</p>
          )}

          {tags.length ? (
            <div className="flex flex-wrap gap-2">
              {tags.map((tag) => (
                <span key={`${shop.id}-${tag}`} className="rounded-full bg-[#f2eee5] px-3 py-1 text-xs font-bold text-zinc-600">
                  {tag}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      </article>
    </Link>
  );
}

export default async function Home() {
  const [categoriesRes, shopCountRes, aiHealthRes] = await Promise.all([
    javaApi.listCategories().catch(() => ({ data: [] as Category[] })),
    javaApi.shopCount().catch(() => ({ data: 0 })),
    aiApi.health().catch(() => ({ status: "off" })),
  ]);

  const categories = (categoriesRes.data ?? []) as Category[];
  const totalShops = shopCountRes.data ?? 0;
  const aiOk = aiHealthRes.status === "ok";

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

  return (
    <main className="min-h-screen bg-[#f6f1e8] text-[#171512]">
      <section className="border-b border-black/10 bg-[#f6f1e8]">
        <div className="mx-auto grid min-h-[560px] max-w-7xl gap-10 px-6 py-12 md:grid-cols-[1fr_0.9fr] md:px-12 md:py-20">
          <div className="flex flex-col justify-center">
            <p className="text-sm font-black tracking-[0.22em] text-[#b89f61]">獨家桌位，僅此一處</p>
            <h1 className="mt-6 max-w-2xl text-6xl font-black leading-[0.92] tracking-[-0.08em] md:text-8xl">
              餐飲體驗
              <span className="block text-[#b89f61]">臻於極致</span>
            </h1>
            <p className="mt-8 max-w-xl text-lg leading-8 text-zinc-600">
              ByteBites 只展示值得花時間看的餐廳。你可以直接探索分類，也可以交給 AI 助手從推薦、空位、訂金付款一路處理到完成訂位。
            </p>
          </div>

          <div className="flex items-center">
            <div className="w-full rounded-[2rem] border border-black/10 bg-[#eee8dc] p-8">
              <div className="mb-6 flex items-center gap-3">
                <Sparkles className="h-7 w-7 fill-[#171512] text-[#171512]" />
                <div>
                  <h2 className="text-3xl font-black">今晚想去哪？</h2>
                  <p className="mt-1 text-zinc-600">用自然語言找最適合的一間</p>
                </div>
              </div>

              <Link
                href="/ai"
                className="flex items-center gap-3 rounded-2xl border border-black/10 bg-[#f8f5ee] px-5 py-5 text-left text-zinc-500 transition hover:border-[#b89f61]/60 hover:bg-white"
              >
                <Search className="h-5 w-5" />
                <span className="flex-1 text-base font-bold">找餐廳、查空位、直接訂位</span>
                <Bot className={`h-5 w-5 ${aiOk ? "text-emerald-700" : "text-zinc-400"}`} />
              </Link>

              <div className="mt-6 flex flex-wrap gap-3">
                {AI_PROMPTS.map((prompt) => (
                  <Link key={prompt} href={`/ai?q=${encodeURIComponent(prompt)}`}>
                    <span className="inline-flex rounded-xl bg-[#e7dfcf] px-4 py-3 text-sm font-black text-zinc-600 transition hover:bg-[#ded2bc]">
                      {prompt}
                    </span>
                  </Link>
                ))}
              </div>

              <div className="mt-7 grid grid-cols-2 gap-3 border-t border-black/10 pt-6 text-sm">
                <div>
                  <p className="font-mono text-2xl font-black">{totalShops || "—"}</p>
                  <p className="text-zinc-500">間餐廳資料</p>
                </div>
                <div>
                  <p className="font-mono text-2xl font-black">{aiOk ? "ONLINE" : "OFFLINE"}</p>
                  <p className="text-zinc-500">AI Agent 狀態</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <CategoryRail categories={categories} />

      <section className="px-6 py-14 md:px-12">
        <div className="mx-auto max-w-7xl">
          <div className="mb-8 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="text-xs font-black tracking-[0.22em] text-[#b89f61]">得獎紀錄與熱門口碑</p>
              <h2 className="mt-2 text-4xl font-black tracking-[-0.04em]">值得優先看的餐廳</h2>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-zinc-500">
                依照片完整度、真實資料品質、捷運熱門度與評分排序。想要更精準，直接到 AI 助手描述今天的需求。
              </p>
            </div>
            <Link href="/shops" className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-white px-5 py-3 text-sm font-black hover:bg-[#fbfaf6]">
              查看全部
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>

          {featuredItems.length ? (
            <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
              {featuredItems.map((item) => (
                <FeaturedShopCard key={item.shop.id} item={item} metadata={metadataMap.get(item.shop.id)} />
              ))}
            </div>
          ) : (
            <div className="rounded-[2rem] border border-black/10 bg-white p-10 text-center text-zinc-500">
              目前尚無可展示餐廳。請確認後端資料與圖片 manifest。
            </div>
          )}
        </div>
      </section>

      <section className="px-6 pb-20 md:px-12">
        <div className="mx-auto grid max-w-7xl gap-4 md:grid-cols-3">
          {[
            ["與 AI 助手聊天", "讓 Agent 依照需求推薦、查空位並保留訂位。", "/ai"],
            ["空位釋出通知", "額滿時段可建立 watch，有位時主動提醒。", "/notifications"],
            ["我的訂位", "查看待付款、已付款與已取消紀錄。", "/my-bookings"],
          ].map(([title, body, href]) => (
            <Link key={title} href={href} className="rounded-[1.75rem] border border-black/10 bg-white p-6 shadow-sm transition hover:-translate-y-1 hover:shadow-lg">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <h3 className="text-xl font-black">{title}</h3>
                  <p className="mt-2 text-sm leading-6 text-zinc-500">{body}</p>
                </div>
                <CalendarDays className="h-6 w-6 text-[#b89f61]" />
              </div>
            </Link>
          ))}
        </div>
      </section>
    </main>
  );
}
