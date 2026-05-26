import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, Star, MessageSquare, DollarSign, MapPin, Phone } from "lucide-react";
import { Button } from "@/components/ui/button";
import { javaApi, type ShopAiMetadata, type VoucherOffer } from "@/lib/api";
import { getStyleByTypeId } from "@/lib/categoryStyle";
import { BookingButton } from "@/components/BookingButton";

export default async function ShopDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  const [shopRes, aiRes, voucherRes, hotSeatRes] = await Promise.all([
    javaApi.shopDetail(Number(id)).catch(() => null),
    javaApi.shopAiMetadata(id).catch(() => ({ success: false, data: null })),
    javaApi.shopVouchers(Number(id)).catch(() => ({ success: false, data: [] as VoucherOffer[] })),
    javaApi.hotSeatVouchers(Number(id)).catch(() => ({ success: false, data: [] as { id: number; stock: number }[] })),
  ]);

  const shop = shopRes?.data;
  if (!shop) return notFound();

  const ai: ShopAiMetadata | null = aiRes?.data ?? null;
  const vouchers = (voucherRes?.data ?? []) as VoucherOffer[];
  const style = getStyleByTypeId(shop.typeId);
  const Icon = style.icon;

  const hotSeatStockMap = new Map(
    (hotSeatRes?.data ?? []).map((offer) => [offer.id, offer.stock]),
  );
  const hotSeatOffers = vouchers
    .filter((voucher) => voucher.type === 1)
    .map((voucher) => ({
      ...voucher,
      stock: hotSeatStockMap.get(voucher.id) ?? voucher.stock ?? 0,
      saving: Math.max((voucher.actualValue ?? 0) - (voucher.payValue ?? 0), 0),
    }))
    .filter((voucher) => (voucher.stock ?? 0) > 0);
  const merchantOffers = vouchers.filter((voucher) => voucher.type === 0);
  const bestHotSeatOffer = [...hotSeatOffers].sort((a, b) => {
    const savingDiff = (b.saving ?? 0) - (a.saving ?? 0);
    if (savingDiff !== 0) return savingDiff;
    return (a.stock ?? 0) - (b.stock ?? 0);
  })[0] ?? null;

  const parseTags = (raw: string | undefined): string[] => {
    if (!raw) return [];
    try {
      return typeof raw === "string" ? JSON.parse(raw) : (raw as string[]);
    } catch {
      return [];
    }
  };

  const formatCurrency = (amount?: number) =>
    amount ? `NT$ ${(amount / 100).toLocaleString()}` : "—";

  const formatWindow = (start?: string, end?: string) => {
    if (!start || !end) return "限量開放中";
    return `${start.slice(5, 16).replace("T", " ")} - ${end.slice(5, 16).replace("T", " ")}`;
  };

  const formatShortDate = (value?: string) => {
    if (!value) return null;
    return value.slice(5, 16).replace("T", " ");
  };

  const getUrgencyTone = (stock?: number) => {
    if ((stock ?? 0) <= 10) return "text-red-600 bg-red-50 border-red-200";
    if ((stock ?? 0) <= 25) return "text-amber-700 bg-amber-50 border-amber-200";
    return "text-emerald-700 bg-emerald-50 border-emerald-200";
  };

  const bookingAdvice = (() => {
    if (bestHotSeatOffer) {
      const stock = bestHotSeatOffer.stock ?? 0;
      if (stock <= 10) {
        return {
          title: "現在最適合先搶 Hot Seat",
          body: `這家店目前有熱門時段限量名額，剩 ${stock} 席，先鎖位比直接等現場更穩。`,
        };
      }
      return {
        title: "熱門時段建議先看 Hot Seat",
        body: `目前還有 ${stock} 個限量名額，若你想訂晚餐熱門時段，先搶位通常比一般訂位更有把握。`,
      };
    }
    if (ai?.bookingDifficulty === "預約困難") {
      return {
        title: "這家店熱門時段較難訂",
        body: "目前雖然沒有上架 Hot Seat 方案，但晚餐尖峰時段仍建議提早安排。",
      };
    }
    return {
      title: "目前可直接一般訂位",
      body: "如果你只是想先卡位，直接走一般訂位流程即可；若後續有 Hot Seat 方案上架，也會在此頁顯示。",
    };
  })();

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

      <section className="max-w-4xl mx-auto px-4 md:px-8 mt-10">
        <div className="rounded-2xl border bg-muted/20 p-5 md:p-6">
          <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <div className="max-w-2xl">
              <div className="text-xs font-mono text-muted-foreground">BOOKING STRATEGY</div>
              <h2 className="text-lg font-semibold mt-1">{bookingAdvice.title}</h2>
              <p className="text-sm text-muted-foreground mt-2">{bookingAdvice.body}</p>
            </div>
            {bestHotSeatOffer ? (
              <a
                href="#offers"
                className="inline-flex items-center justify-center rounded-lg border px-4 py-2 text-sm font-medium hover:bg-background"
              >
                查看 Hot Seat 方案
              </a>
            ) : null}
          </div>
        </div>
      </section>

      {(hotSeatOffers.length > 0 || merchantOffers.length > 0) && (
        <section id="offers" className="max-w-4xl mx-auto px-4 md:px-8 mt-10 space-y-6">
          <div>
            <h2 className="text-lg font-semibold mb-2">現在可訂方案</h2>
            <p className="text-sm text-muted-foreground">
              一般訂位是直接選時段；Hot Seat 是熱門時段限量搶位，名額賣完就沒了。
            </p>
          </div>

          {hotSeatOffers.length > 0 && (
            <div>
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-medium">Hot Seat 限時搶位</h3>
                <span className="text-xs rounded-full bg-primary/10 text-primary px-2 py-1">
                  熱門時段限量
                </span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {hotSeatOffers.map((offer) => {
                  const stock = offer.stock ?? 0;
                  const discount = offer.actualValue > 0
                    ? Math.round((offer.payValue / offer.actualValue) * 100)
                    : null;
                  const isBest = bestHotSeatOffer?.id === offer.id;
                  return (
                    <div key={offer.id} className="rounded-xl border border-primary/20 bg-primary/[0.03] p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <div className="font-medium">{offer.title}</div>
                            {isBest ? (
                              <span className="rounded-full bg-primary px-2 py-0.5 text-[11px] font-medium text-primary-foreground">
                                最佳方案
                              </span>
                            ) : null}
                          </div>
                          {offer.subTitle ? (
                            <div className="text-sm text-muted-foreground mt-1">{offer.subTitle}</div>
                          ) : null}
                        </div>
                        <div className={`text-right shrink-0 rounded-lg border px-3 py-2 ${getUrgencyTone(stock)}`}>
                          <div className="text-xs text-muted-foreground">剩餘名額</div>
                          <div className="text-2xl font-bold">{stock}</div>
                        </div>
                      </div>

                      <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mt-4 text-sm">
                        <div className="rounded-lg bg-background p-3 border">
                          <div className="text-xs text-muted-foreground">搶位價</div>
                          <div className="font-semibold mt-1">{formatCurrency(offer.payValue)}</div>
                        </div>
                        <div className="rounded-lg bg-background p-3 border">
                          <div className="text-xs text-muted-foreground">原價值</div>
                          <div className="font-semibold mt-1">
                            {formatCurrency(offer.actualValue)}
                            {discount ? <span className="text-xs text-primary ml-2">{discount} 折</span> : null}
                          </div>
                        </div>
                        <div className="rounded-lg bg-background p-3 border col-span-2 md:col-span-1">
                          <div className="text-xs text-muted-foreground">立刻省下</div>
                          <div className="font-semibold mt-1 text-primary">{formatCurrency(offer.saving)}</div>
                        </div>
                      </div>

                      <div className="mt-3 space-y-1 text-xs text-muted-foreground">
                        <p>開放時間：{formatWindow(offer.beginTime, offer.endTime)}</p>
                        {offer.endTime ? <p>最後可搶：{formatShortDate(offer.endTime)}</p> : null}
                        {offer.rules ? <p>使用規則：{offer.rules}</p> : null}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {merchantOffers.length > 0 && (
            <div>
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-medium">商家優惠</h3>
                <span className="text-xs rounded-full bg-muted px-2 py-1 text-muted-foreground">
                  一般餐券 / 套餐
                </span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {merchantOffers.map((offer) => (
                  <div key={offer.id} className="rounded-xl border p-4">
                    <div className="font-medium">{offer.title}</div>
                    {offer.subTitle ? (
                      <div className="text-sm text-muted-foreground mt-1">{offer.subTitle}</div>
                    ) : null}
                    <div className="flex items-center gap-2 mt-3">
                      <span className="font-semibold">{formatCurrency(offer.payValue)}</span>
                      <span className="text-xs text-muted-foreground line-through">
                        {formatCurrency(offer.actualValue)}
                      </span>
                    </div>
                    {offer.rules ? (
                      <p className="text-xs text-muted-foreground mt-3">使用規則：{offer.rules}</p>
                    ) : null}
                  </div>
                ))}
              </div>
            </div>
          )}
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
        <div className="relative max-w-4xl mx-auto px-4 md:px-8 py-3 flex items-center justify-between">
          <div className="text-sm">
            <div className="font-medium">{shop.name}</div>
            <div className="text-muted-foreground text-xs">
              {bestHotSeatOffer
                ? `Hot Seat 剩 ${bestHotSeatOffer.stock} 席`
                : ai?.bookingDifficulty === "預約困難"
                  ? "熱門時段需提前預約"
                  : "可線上訂位"}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {bestHotSeatOffer ? (
              <a
                href="#offers"
                className="hidden md:inline-flex rounded-lg border px-3 py-2 text-sm hover:bg-muted"
              >
                看 Hot Seat
              </a>
            ) : null}
            <BookingButton shop={{ id: shop.id, name: shop.name, avgPrice: shop.avgPrice }} />
          </div>
        </div>
      </div>
    </div>
  );
}
