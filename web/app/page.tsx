import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { aiApi, javaApi, type Category } from "@/lib/api";

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
    <main className="mx-auto min-h-screen max-w-5xl p-8">
      <h1 className="mb-2 text-3xl font-bold">ByteBites</h1>
      <p className="text-muted-foreground mb-8">
        台灣在地點評平台 + AI 應用整合
      </p>

      <div className="mb-8 grid grid-cols-1 gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Java Backend</CardTitle>
          </CardHeader>
          <CardContent>
            <span className={categories.length ? "text-green-600" : "text-red-600"}>
              {categories.length ? `✓ ${categories.length} categories` : "✗ unreachable"}
            </span>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">MRT Stations</CardTitle>
          </CardHeader>
          <CardContent>
            <span className={mrt.length ? "text-green-600" : "text-red-600"}>
              {mrt.length ? `✓ ${mrt.length} stations` : "✗ unreachable"}
            </span>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">AI Service</CardTitle>
          </CardHeader>
          <CardContent>
            <span className={aiOk ? "text-green-600" : "text-red-600"}>
              {aiOk ? "✓ healthy" : "✗ unreachable"}
            </span>
          </CardContent>
        </Card>
      </div>

      <Link href="/ai">
        <Card className="mb-8 cursor-pointer border-primary/50 transition hover:shadow-lg">
          <CardContent className="flex items-center gap-4 p-6">
            <div className="text-4xl">✨</div>
            <div>
              <div className="text-lg font-semibold">AI 智能搜尋</div>
              <div className="text-muted-foreground text-sm">
                語意搜尋、智能推薦、Agent 自動選工具
              </div>
            </div>
          </CardContent>
        </Card>
      </Link>

      <h2 className="mb-4 text-xl font-semibold">分類</h2>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {categories.map((category) => (
          <Link key={category.id} href={`/shops?category=${category.slug}`}>
            <Card className="cursor-pointer transition hover:shadow-md">
              <CardContent className="p-4">
                <div className="font-medium">{category.name}</div>
                <div className="text-muted-foreground text-xs">{category.slug}</div>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </main>
  );
}
