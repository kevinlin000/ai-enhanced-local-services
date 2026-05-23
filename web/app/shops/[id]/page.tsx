import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { javaApi, type Shop, type ShopAiMetadata } from "@/lib/api";
import { getStyleByTypeId } from "@/lib/categoryStyle";

export default async function ShopDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let shop: Shop | undefined;
  let ai: ShopAiMetadata | null = null;
  try {
    const [shopRes, aiRes] = await Promise.all([
      javaApi.shopDetail(Number(id)),
      javaApi.shopAiMetadata(id).catch(() => ({ success: false, data: null })),
    ]);
    shop = shopRes.data;
    ai = aiRes?.data ?? null;
    if (!shop) return notFound();
  } catch {
    return notFound();
  }

  let hours: Record<string, string> = {};
  try {
    if (shop.businessHours) hours = JSON.parse(shop.businessHours);
  } catch {}

  const { icon: Icon, gradient } = getStyleByTypeId(shop.typeId);

  const dayMap: Record<string, string> = {
    mon: "週一",
    tue: "週二",
    wed: "週三",
    thu: "週四",
    fri: "週五",
    sat: "週六",
    sun: "週日",
  };

  const parseTags = (raw: string | undefined): string[] => {
    if (!raw) return [];
    try {
      return typeof raw === "string" ? JSON.parse(raw) : raw;
    } catch {
      return [];
    }
  };

  return (
    <main className="mx-auto min-h-screen max-w-3xl px-4 py-8 md:px-8">
      <div className={`-mt-8 -mx-8 mb-8 flex h-40 items-center justify-center bg-gradient-to-br ${gradient}`}>
        <Icon className="h-16 w-16 text-foreground/40" strokeWidth={1.5} />
      </div>

      <Link href="/shops">
        <Button variant="ghost" size="sm" className="mb-4">
          <ArrowLeft className="mr-1 h-4 w-4" />
          返回
        </Button>
      </Link>

      <div className="mb-2 flex items-start justify-between gap-4">
        <h1 className="text-3xl font-bold">{shop.name}</h1>
        {shop.score ? (
          <Badge variant="secondary" className="text-base">
            {(shop.score / 10).toFixed(1)}
          </Badge>
        ) : null}
      </div>

      <div className="text-muted-foreground mb-6">
        {shop.district ? <span>📍 {shop.district}</span> : null}
        {shop.mrtStation ? <span> · 捷運{shop.mrtStation}站</span> : null}
      </div>

      <Card className="mb-4">
        <CardContent className="space-y-3 p-6">
          {shop.address ? (
            <div>
              <span className="text-muted-foreground">地址：</span>
              {shop.address}
            </div>
          ) : null}
          {shop.avgPrice ? (
            <div>
              <span className="text-muted-foreground">平均消費：</span>${shop.avgPrice}
            </div>
          ) : null}
          {shop.priceRange ? (
            <div>
              <span className="text-muted-foreground">價位等級：</span>
              {"$".repeat(shop.priceRange)}
            </div>
          ) : null}
        </CardContent>
      </Card>

      {Object.keys(hours).length > 0 ? (
        <Card className="mb-4">
          <CardContent className="p-6">
            <h2 className="mb-3 font-semibold">營業時間</h2>
            <Separator className="mb-3" />
            <div className="space-y-1 text-sm">
              {Object.entries(hours).map(([day, time]) => (
                <div key={day} className="flex justify-between gap-4">
                  <span className="text-muted-foreground">{dayMap[day] ?? day}</span>
                  <span>{time}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : null}

      {ai && (
        <div className="mt-6 space-y-6">
          {ai.aiSummary && (
            <section>
              <h2 className="text-lg font-semibold mb-2">關於這家店</h2>
              <p className="text-foreground/80 leading-relaxed">{ai.aiSummary}</p>
            </section>
          )}

          {ai.highlightReview && (
            <section className="bg-primary/5 border-l-4 border-primary p-4 rounded-r">
              <p className="text-sm italic">「{ai.highlightReview}」</p>
              <p className="text-xs text-muted-foreground mt-1">— AI 摘自評論</p>
            </section>
          )}

          {parseTags(ai.signatureDishes).length > 0 && (
            <section>
              <h2 className="text-lg font-semibold mb-2">招牌菜</h2>
              <div className="flex flex-wrap gap-2">
                {parseTags(ai.signatureDishes).map((d) => (
                  <span key={d} className="px-3 py-1 rounded-full bg-muted text-sm">
                    {d}
                  </span>
                ))}
              </div>
            </section>
          )}

          {parseTags(ai.atmosphereTags).length > 0 && (
            <section>
              <h2 className="text-lg font-semibold mb-2">適合場景</h2>
              <div className="flex flex-wrap gap-2">
                {parseTags(ai.atmosphereTags).map((t) => (
                  <span key={t} className="px-3 py-1 rounded-full bg-primary/10 text-primary text-sm">
                    {t}
                  </span>
                ))}
              </div>
            </section>
          )}

          <div className="grid grid-cols-2 gap-4 text-sm">
            {ai.bookingDifficulty && (
              <div>
                <div className="text-muted-foreground">預約難度</div>
                <div className="font-medium">{ai.bookingDifficulty}</div>
              </div>
            )}
            {ai.pricePerPerson && (
              <div>
                <div className="text-muted-foreground">參考價位</div>
                <div className="font-medium">{ai.pricePerPerson}</div>
              </div>
            )}
            {ai.phone && (
              <div>
                <div className="text-muted-foreground">電話</div>
                <div className="font-medium font-mono">{ai.phone}</div>
              </div>
            )}
          </div>
        </div>
      )}
    </main>
  );
}
