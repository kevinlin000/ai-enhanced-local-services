import Link from "next/link";
import { Button } from "@/components/ui/button";
import { aiApi, javaApi, type Category } from "@/lib/api";
import { getCategoryStyle } from "@/lib/categoryStyle";

export default async function Home() {
  let categories: Category[] = [];
  let mrt: unknown[] = [];
  let aiOk = false;

  try {
    const c = await javaApi.listCategories();
    categories = (c.data ?? []) as Category[];
  } catch {}

  try {
    const m = await javaApi.listMrtStations();
    mrt = m.data ?? [];
  } catch {}

  try {
    const a = await aiApi.health();
    aiOk = a.status === "ok";
  } catch {}

  return (
    <main>
      <section className="mx-auto max-w-5xl px-8 py-20">
        <div className="text-muted-foreground font-mono mb-2 text-sm tracking-wide">
          ByteBites · v1.0 · Taiwan
        </div>
        <h1 className="mb-4 text-5xl font-bold tracking-tight md:text-6xl">
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

      <section className="mx-auto grid max-w-5xl grid-cols-2 gap-8 border-y px-8 py-8 text-sm md:grid-cols-4">
        <div>
          <div className="font-mono text-3xl font-bold">{categories.length || "—"}</div>
          <div className="text-muted-foreground mt-1">在地分類</div>
        </div>
        <div>
          <div className="font-mono text-3xl font-bold">{mrt.length || "—"}</div>
          <div className="text-muted-foreground mt-1">捷運站</div>
        </div>
        <div>
          <div className="font-mono text-3xl font-bold">25</div>
          <div className="text-muted-foreground mt-1">精選店家</div>
        </div>
        <div>
          <div className="font-mono text-3xl font-bold">{aiOk ? "ON" : "OFF"}</div>
          <div className="text-muted-foreground mt-1">AI 服務</div>
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-8 py-12">
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
