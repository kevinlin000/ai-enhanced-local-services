import Link from "next/link";
import { Button } from "@/components/ui/button";
import { aiApi, javaApi, type Category, type Shop, type ShopAiMetadata } from "@/lib/api";
import { getCategoryStyle, getStyleByTypeId } from "@/lib/categoryStyle";

const HOT_STATIONS = [
  "信義安和", "台北101/世貿", "市政府", "象山",
  "中山國小", "雙連", "行天宮", "中山",
];

const HOME_AI_QUICK_LINKS = [
  { label: "高級火鍋", href: "/shops?mode=ai&q=中山站附近高級火鍋" },
  { label: "約會餐廳", href: "/shops?mode=ai&q=適合約會的高級餐廳" },
  { label: "Hot Seat", href: "/shops?mode=ai&q=有 Hot Seat 的熱門餐廳" },
  { label: "商務請客", href: "/shops?mode=ai&q=適合商務請客的台菜" },
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
    .map((name, idx) => ({ name, shops: stationShops[idx]?.data ?? [] }))
    .filter((s) => s.shops.length > 0)
    .sort((a, b) => b.shops.length - a.shops.length);

  const featuredShops = stationsWithShops.flatMap((station) => station.shops.slice(0, 3));
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
    <main>
      <section className="mx-auto max-w-5xl px-4 py-20 md:px-8">
        <div className="text-muted-foreground font-mono mb-2 text-sm tracking-wide">
          ByteBites · v1.0 · Taiwan
        </div>
        <h1 className="mb-4 text-4xl font-bold tracking-tight md:text-6xl">
          台灣在地
          <br />
          <span className="text-primary">AI 點評平台</span>
        </h1>
        <p className="text-muted-foreground mb-8 max-w-xl text-lg">
          用自然語言找台北餐廳。看 AI 摘要、預約難度、Hot Seat 熱門時段方案。
        </p>
        <div className="flex flex-wrap gap-3">
          <Link href="/ai">
            <Button size="lg" className="bg-primary hover:bg-primary/90">
              開始 AI 搜尋 →
            </Button>
          </Link>
          <Link href="/shops">
            <Button size="lg" variant="outline">
              瀏覽店家
            </Button>
          </Link>
        </div>
        <div className="mt-5 flex flex-wrap gap-2">
          {HOME_AI_QUICK_LINKS.map((item) => (
            <Link key={item.label} href={item.href}>
              <span className="inline-flex rounded-full border border-primary/30 bg-primary/5 px-3 py-1.5 text-xs text-primary transition-colors hover:bg-primary/10">
                {item.label}
              </span>
            </Link>
          ))}
        </div>
      </section>

      <section className="mx-auto grid max-w-5xl grid-cols-2 gap-8 border-y px-4 py-8 text-sm md:grid-cols-4 md:px-8">
        <div>
          <div className="font-mono text-3xl font-bold">{categories.length || "—"}</div>
          <div className="text-muted-foreground mt-1">在地分類</div>
        </div>
        <div>
          <div className="font-mono text-3xl font-bold">{stationsWithShops.length || "—"}</div>
          <div className="text-muted-foreground mt-1">捷運站</div>
        </div>
        <div>
          <div className="font-mono text-3xl font-bold">{totalShops || "—"}</div>
          <div className="text-muted-foreground mt-1">在地店家</div>
        </div>
        <div>
          <div className="font-mono text-3xl font-bold">{aiOk ? "ON" : "OFF"}</div>
          <div className="text-muted-foreground mt-1">AI 服務</div>
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-4 py-12 md:px-8">
        <h2 className="mb-1 text-2xl font-semibold">捷運站熱門</h2>
        <p className="text-muted-foreground mb-6 text-sm">8 個捷運站、依店數排序、空站自動隱藏</p>

        <div className="space-y-8">
          {stationsWithShops.map(({ name: station, shops }) => {
            return (
              <div key={station}>
                <div className="mb-3 flex items-baseline justify-between">
                  <h3 className="font-medium">
                    捷運<span className="text-primary">{station}</span>站
                  </h3>
                  <span className="text-muted-foreground font-mono text-xs">{shops.length} 家</span>
                </div>
                <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                  {shops.slice(0, 3).map((shop) => {
                    const style = getStyleByTypeId(shop.typeId);
                    const Icon = style.icon;
                    return (
                      <Link key={shop.id} href={`/shops/${shop.id}`}>
                        <div className="overflow-hidden rounded-xl border transition hover:border-foreground/40 hover:shadow-md">
                          <div className={`flex h-16 items-center justify-center bg-gradient-to-br ${style.gradient}`}>
                            <Icon className="h-7 w-7 text-foreground/40" strokeWidth={1.5} />
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
                            {shop.avgPrice ? (
                              <div className="text-muted-foreground font-mono mt-1 text-xs">
                                NT$ {shop.avgPrice}
                              </div>
                            ) : null}
                            {metadataMap.get(shop.id)?.pricePerPerson ? (
                              <div className="text-muted-foreground mt-1 text-xs">
                                價位：{metadataMap.get(shop.id)?.pricePerPerson}
                              </div>
                            ) : null}
                            {metadataMap.get(shop.id)?.bookingDifficulty ? (
                              <div className="mt-1 text-xs text-foreground/80">
                                {metadataMap.get(shop.id)?.bookingDifficulty}
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

      <section className="mx-auto max-w-5xl px-4 py-12 md:px-8">
        <h2 className="mb-1 text-2xl font-semibold">12 個在地分類</h2>
        <p className="text-muted-foreground mb-6 text-sm">
          從牛肉麵到手搖飲、依台灣口味分
        </p>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4">
          {categories.map((category) => {
            const { icon: Icon, gradient } = getCategoryStyle(category.slug);
            return (
              <Link key={category.id} href={`/shops?category=${category.slug}`}>
                <div
                  className={`relative flex h-32 flex-col justify-between overflow-hidden rounded-xl border bg-gradient-to-br p-5 transition hover:border-foreground/40 hover:shadow-sm ${gradient}`}
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
      </section>
    </main>
  );
}
