import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { javaApi, type Category, type Shop } from "@/lib/api";
import { getCategoryStyle } from "@/lib/categoryStyle";

export default async function ShopsPage({
  searchParams,
}: {
  searchParams: Promise<{ category?: string }>;
}) {
  const { category } = await searchParams;
  const slug = category ?? "beef-noodle";

  const [catRes, shopRes] = await Promise.all([
    javaApi.listCategories().catch(() => ({ data: [] as Category[] })),
    javaApi.shopsByCategory(slug).catch(() => ({ data: [] as Shop[] })),
  ]);

  const categories = catRes.data;
  const shops = shopRes.data;
  const { icon: Icon, gradient } = getCategoryStyle(slug);

  return (
    <main className="mx-auto min-h-screen max-w-6xl p-8">
      <h1 className="mb-2 text-3xl font-bold">商家</h1>
      <p className="text-muted-foreground mb-6">瀏覽台北在地店家</p>

      <div className="mb-8 flex flex-wrap gap-2">
        {categories.map((c) => (
          <Link key={c.id} href={`/shops?category=${c.slug}`}>
            <Badge
              variant={c.slug === slug ? "default" : "outline"}
              className="cursor-pointer rounded-full px-3 py-1 text-sm"
            >
              {c.name}
            </Badge>
          </Link>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {shops.map((s) => (
          <Link key={s.id} href={`/shops/${s.id}`}>
            <div className="h-full overflow-hidden rounded-xl border bg-card transition hover:border-foreground/40 hover:shadow-md">
              <div className={`flex h-24 items-center justify-center bg-gradient-to-br ${gradient}`}>
                <Icon className="h-10 w-10 text-foreground/40" strokeWidth={1.5} />
              </div>
              <div className="p-4">
                <div className="mb-2 flex items-start justify-between gap-2">
                  <h3 className="leading-tight font-semibold">{s.name}</h3>
                  {s.score ? (
                    <span className="bg-foreground text-background font-mono shrink-0 rounded px-2 py-0.5 text-sm">
                      {(s.score / 10).toFixed(1)}
                    </span>
                  ) : null}
                </div>
                <div className="text-muted-foreground space-y-1 text-xs">
                  {s.district ? (
                    <div className="font-mono">📍 {s.district} · 捷運{s.mrtStation}站</div>
                  ) : null}
                  {s.address ? <div className="truncate">{s.address}</div> : null}
                  {s.avgPrice ? <div className="font-mono">NT$ {s.avgPrice}</div> : null}
                </div>
              </div>
            </div>
          </Link>
        ))}
      </div>

      {shops.length === 0 ? (
        <div className="text-muted-foreground py-12 text-center">
          此分類目前無店家
        </div>
      ) : null}
    </main>
  );
}
