import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { javaApi, type Category, type Shop } from "@/lib/api";

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
            <div className="hover:border-foreground/40 h-full rounded-xl border bg-card p-4 transition">
              <div className="mb-2 flex items-start justify-between gap-4">
                <h3 className="text-lg font-semibold">{s.name}</h3>
                {s.score ? (
                  <div className="font-mono text-sm">{(s.score / 10).toFixed(1)}</div>
                ) : null}
              </div>
              <div className="text-muted-foreground space-y-1 text-sm">
                {s.district ? <div>📍 {s.district} · 捷運{s.mrtStation}站</div> : null}
                {s.address ? <div className="truncate">{s.address}</div> : null}
                {s.avgPrice ? <div>平均 ${s.avgPrice}</div> : null}
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
