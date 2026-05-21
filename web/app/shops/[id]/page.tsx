import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { javaApi, type Shop } from "@/lib/api";
import { getStyleByTypeId } from "@/lib/categoryStyle";

export default async function ShopDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let shop: Shop | undefined;
  try {
    const res = await javaApi.shopDetail(Number(id));
    shop = res.data;
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
        <Card>
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
    </main>
  );
}
