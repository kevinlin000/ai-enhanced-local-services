import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, Star, MessageSquare, DollarSign, MapPin, Phone } from "lucide-react";
import { Button } from "@/components/ui/button";
import { javaApi, type ShopAiMetadata } from "@/lib/api";
import { getStyleByTypeId } from "@/lib/categoryStyle";

export default async function ShopDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  const [shopRes, aiRes] = await Promise.all([
    javaApi.shopDetail(Number(id)).catch(() => null),
    javaApi.shopAiMetadata(id).catch(() => ({ success: false, data: null })),
  ]);

  const shop = shopRes?.data;
  if (!shop) return notFound();

  const ai: ShopAiMetadata | null = aiRes?.data ?? null;
  const style = getStyleByTypeId(shop.typeId);
  const Icon = style.icon;

  const parseTags = (raw: string | undefined): string[] => {
    if (!raw) return [];
    try {
      return typeof raw === "string" ? JSON.parse(raw) : (raw as string[]);
    } catch {
      return [];
    }
  };

  const dishes = parseTags(ai?.signatureDishes);
  const tags = parseTags(ai?.atmosphereTags);

  return (
    <div className="min-h-screen pb-32">
      {/* Back */}
      <div className="max-w-4xl mx-auto px-4 md:px-8 pt-6">
        <Link href="/shops">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="h-4 w-4 mr-1" />返回
          </Button>
        </Link>
      </div>

      {/* Hero */}
      <section className="max-w-4xl mx-auto px-4 md:px-8 mt-4">
        <div className={`bg-gradient-to-br ${style.gradient} rounded-2xl p-6 md:p-10`}>
          <div className="flex items-start gap-4">
            <div className="hidden md:flex h-16 w-16 rounded-xl bg-background/60 backdrop-blur items-center justify-center shrink-0">
              <Icon className="h-8 w-8 text-foreground/60" strokeWidth={1.5} />
            </div>
            <div className="flex-1">
              <div className="flex flex-wrap gap-2 mb-2">
                <span className="text-xs px-2 py-0.5 rounded-full bg-background/60 backdrop-blur">
                  {style.label}
                </span>
                {shop.district && (
                  <span className="text-xs px-2 py-0.5 rounded-full bg-background/60 backdrop-blur">
                    📍 {shop.district}
                  </span>
                )}
              </div>
              <h1 className="text-2xl md:text-4xl font-bold tracking-tight">
                {shop.name}
              </h1>
              {shop.address && (
                <p className="text-sm text-foreground/70 mt-2">{shop.address}</p>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Stats */}
      <section className="max-w-4xl mx-auto px-4 md:px-8 mt-6">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="rounded-xl border p-4">
            <div className="flex items-center gap-2 text-muted-foreground text-xs mb-1">
              <Star className="h-3.5 w-3.5" /> 評分
            </div>
            <div className="font-mono text-2xl font-bold">
              {shop.score ? (shop.score / 10).toFixed(1) : "—"}
            </div>
          </div>
          <div className="rounded-xl border p-4">
            <div className="flex items-center gap-2 text-muted-foreground text-xs mb-1">
              <MessageSquare className="h-3.5 w-3.5" /> 評論數
            </div>
            <div className="font-mono text-2xl font-bold">
              {shop.comments?.toLocaleString() ?? "—"}
            </div>
          </div>
          <div className="rounded-xl border p-4">
            <div className="flex items-center gap-2 text-muted-foreground text-xs mb-1">
              <DollarSign className="h-3.5 w-3.5" /> 平均消費
            </div>
            <div className="font-mono text-2xl font-bold">
              {shop.avgPrice ? `$${shop.avgPrice}` : "—"}
            </div>
          </div>
          <div className="rounded-xl border p-4">
            <div className="flex items-center gap-2 text-muted-foreground text-xs mb-1">
              <MapPin className="h-3.5 w-3.5" /> 區域
            </div>
            <div className="text-2xl font-bold">
              {shop.district ?? shop.area ?? "—"}
            </div>
          </div>
        </div>
      </section>

      {/* AI Section */}
      {ai && (
        <section className="max-w-4xl mx-auto px-4 md:px-8 mt-10 space-y-6">
          {ai.aiSummary && (
            <div>
              <h2 className="text-lg font-semibold mb-2">關於這家店</h2>
              <p className="text-foreground/80 leading-relaxed">{ai.aiSummary}</p>
            </div>
          )}

          {ai.highlightReview && (
            <div className="bg-primary/5 border-l-4 border-primary p-4 rounded-r">
              <p className="text-sm italic">「{ai.highlightReview}」</p>
              <p className="text-xs text-muted-foreground mt-1">— AI 摘自評論</p>
            </div>
          )}

          {dishes.length > 0 && (
            <div>
              <h2 className="text-lg font-semibold mb-2">招牌菜</h2>
              <div className="flex flex-wrap gap-2">
                {dishes.map((d) => (
                  <span key={d} className="px-3 py-1 rounded-full bg-muted text-sm">
                    {d}
                  </span>
                ))}
              </div>
            </div>
          )}

          {tags.length > 0 && (
            <div>
              <h2 className="text-lg font-semibold mb-2">適合場景</h2>
              <div className="flex flex-wrap gap-2">
                {tags.map((t) => (
                  <span key={t} className="px-3 py-1 rounded-full bg-primary/10 text-primary text-sm">
                    {t}
                  </span>
                ))}
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
            {ai.bookingDifficulty && (
              <div className="rounded-xl border p-4">
                <div className="text-muted-foreground text-xs">預約難度</div>
                <div className="font-medium mt-1">{ai.bookingDifficulty}</div>
              </div>
            )}
            {ai.pricePerPerson && (
              <div className="rounded-xl border p-4">
                <div className="text-muted-foreground text-xs">參考價位</div>
                <div className="font-medium mt-1">{ai.pricePerPerson}</div>
              </div>
            )}
            {ai.phone && (
              <div className="rounded-xl border p-4">
                <div className="text-muted-foreground text-xs flex items-center gap-1">
                  <Phone className="h-3 w-3" />電話
                </div>
                <div className="font-medium mt-1 font-mono">{ai.phone}</div>
              </div>
            )}
          </div>
        </section>
      )}

      {/* Map */}
      {shop.x && shop.y && (
        <section className="max-w-4xl mx-auto px-4 md:px-8 mt-10">
          <h2 className="text-lg font-semibold mb-3">地圖位置</h2>
          <div className="rounded-xl overflow-hidden border h-72">
            <iframe
              src={`https://maps.google.com/maps?q=${encodeURIComponent(shop.name + " " + (shop.address ?? ""))}&z=16&output=embed`}
              width="100%"
              height="100%"
              style={{ border: 0 }}
              loading="lazy"
              referrerPolicy="no-referrer-when-downgrade"
            />
          </div>
        </section>
      )}

      {/* Fixed booking CTA */}
      <div className="fixed bottom-0 left-0 right-0 w-full z-30 border-t bg-background/95 backdrop-blur">
        <div className="max-w-4xl mx-auto px-4 md:px-8 py-3 flex items-center justify-between">
          <div className="text-sm">
            <div className="font-medium">{shop.name}</div>
            <div className="text-muted-foreground text-xs">
              {ai?.bookingDifficulty === "預約困難" ? "熱門時段需提前預約" : "可線上訂位"}
            </div>
          </div>
          <Button size="lg" className="bg-primary hover:bg-primary/90">
            立即訂位
          </Button>
        </div>
      </div>
    </div>
  );
}
