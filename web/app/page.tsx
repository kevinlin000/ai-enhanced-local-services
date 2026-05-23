import Link from "next/link";
import { Button } from "@/components/ui/button";
import { aiApi, javaApi, type Category, type Shop } from "@/lib/api";
import { getCategoryStyle, getStyleByTypeId } from "@/lib/categoryStyle";

const HOT_STATIONS = [
  "信義安和", "台北101/世貿", "市政府", "象山",
  "中山國小", "雙連", "行天宮", "中山",
];

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
          用自然語言找台北的店家。RAG 檢索、Agent 自動選工具、評論摘要。
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
                            {shop.avgPrice ? (
                              <div className="text-muted-foreground font-mono mt-1 text-xs">
                                NT$ {shop.avgPrice}
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
