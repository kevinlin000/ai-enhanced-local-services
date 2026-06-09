"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { CalendarDays, ChevronLeft, ChevronRight, DollarSign, Flame, MapPin, Star, Utensils } from "lucide-react";
import type { AbsaAspect } from "@/lib/api";
import type { AgentShop } from "@/lib/agentTypes";
import type { ShopReviewInsights } from "@/lib/reviewInsights";
import { getBestShopCardPhoto } from "@/lib/shopPhotoManifest";
import { proxyImageUrl } from "@/lib/photoProxy";

export type { AgentShop };

// Positive-only framing for recommendation context
const POSITIVE_HIGHLIGHTS: Record<string, string> = {
  dishes: "招牌菜多人讚賞",
  service: "桌邊服務貼心",
  environment: "用餐氛圍舒適",
  price: "性價比受肯定",
};

function StarRating({ rating }: { rating: number }) {
  return (
    <span className="flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((i) => (
        <Star
          key={i}
          className={`h-3 w-3 ${
            rating >= i ? "fill-amber-400 text-amber-400" : "fill-none text-stone-300"
          }`}
        />
      ))}
    </span>
  );
}

function ReviewCarousel({ shopId }: { shopId: number }) {
  const [insights, setInsights] = useState<ShopReviewInsights | null>(null);
  const [idx, setIdx] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/shop/${shopId}/reviews`)
      .then((r) => r.json())
      .then((data: ShopReviewInsights) => setInsights(data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [shopId]);

  const reviews = (insights?.selectedReviews ?? [])
    .filter((review) => review.rating >= 4)
    .slice(0, 3);

  useEffect(() => {
    setIdx(0);
  }, [shopId, reviews.length]);

  if (loading) {
    return (
      <div className="flex flex-col gap-2 animate-pulse">
        <div className="h-3 w-16 rounded bg-muted" />
        <div className="h-16 w-full rounded bg-muted" />
        <div className="h-3 w-24 rounded bg-muted" />
      </div>
    );
  }

  if (!reviews.length) {
    return (
      <div className="rounded-lg bg-muted/60 px-3 py-2 text-xs leading-5 text-muted-foreground">
        目前沒有足夠 4 星以上文字評論可作為推薦亮點；建議進入詳情頁查看完整評論與注意事項。
      </div>
    );
  }

  const review = reviews[idx];
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <StarRating rating={review.rating} />
          <span className="text-[11px] text-muted-foreground truncate max-w-[90px]">
            {review.author}
          </span>
        </div>
        <div className="flex items-center gap-0.5 text-xs text-muted-foreground">
          <button
            onClick={() => setIdx((i) => Math.max(0, i - 1))}
            disabled={idx === 0}
            className="rounded p-0.5 disabled:opacity-30 hover:bg-muted transition"
          >
            <ChevronLeft className="h-3.5 w-3.5" />
          </button>
          <span className="w-8 text-center text-[10px]">
            {idx + 1}/{reviews.length}
          </span>
          <button
            onClick={() => setIdx((i) => Math.min(reviews.length - 1, i + 1))}
            disabled={idx === reviews.length - 1}
            className="rounded p-0.5 disabled:opacity-30 hover:bg-muted transition"
          >
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      <p className="text-sm leading-relaxed text-foreground line-clamp-4">
        {review.text}
      </p>

      {review.labels.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {review.labels.map((label) => (
            <span
              key={label}
              className="rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground"
            >
              {label}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function PositiveHighlights({ shopId }: { shopId: number }) {
  const [highlights, setHighlights] = useState<string[]>([]);

  useEffect(() => {
    fetch(`/api/java/api/shop/${shopId}/absa`)
      .then((r) => r.json())
      .then((d: { data?: { aspects?: string } }) => {
        const raw = d?.data?.aspects;
        if (!raw) return;
        const aspects = JSON.parse(raw) as AbsaAspect[];
        const items = aspects
          .filter((a) => {
            const posCount = (a.positive_evidence ?? []).length;
            const negCount = (a.negative_evidence ?? []).length;
            return a.sentiment === "positive" || (a.sentiment === "mixed" && posCount > negCount);
          })
          .slice(0, 2)
          .map((a) => POSITIVE_HIGHLIGHTS[a.aspect] ?? "")
          .filter(Boolean);
        setHighlights(items);
      })
      .catch(() => {});
  }, [shopId]);

  if (!highlights.length) return null;

  return (
    <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 border-t border-[rgb(222_216_203_/_0.72)] pt-3">
      {highlights.map((h) => (
        <span key={h} className="inline-flex items-center gap-1 text-xs font-medium text-[var(--bb-gold)]">
          <Star className="h-3 w-3" />
          {h}
        </span>
      ))}
    </div>
  );
}

type Props = {
  shop: AgentShop;
  rank: number;
};

export function AgentShopCard({ shop, rank }: Props) {
  const photoUrl = proxyImageUrl(getBestShopCardPhoto(shop.shop_id));
  const mapsQ = encodeURIComponent(
    `${shop.name} ${shop.district ?? ""} 台北`,
  );
  const mapsUrl = `https://maps.google.com/maps?q=${mapsQ}&output=embed&hl=zh-TW`;
  const hasHotSeat = (shop.hot_seat_vouchers?.length ?? 0) > 0;

  return (
    <div data-testid="agent-shop-card" className="bb-premium-surface overflow-hidden rounded-lg">
      {/* Header row: rank + name + hot seat badge */}
      <div className="flex items-center gap-2 border-b px-4 py-2.5">
        <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[var(--bb-gold)] text-[10px] font-medium text-white">
          {rank}
        </span>
        <span className="min-w-0 flex-1 truncate font-medium text-[var(--bb-ink)]">{shop.name}</span>
        {hasHotSeat && (
          <span className="ml-auto inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-800">
            <Flame className="h-3 w-3" />
            Hot Seat 可搶
          </span>
        )}
      </div>

      {/* Three-column grid */}
      <div className="grid grid-cols-1 divide-y md:grid-cols-4 md:divide-x md:divide-y-0">
        {/* Left: photo + meta + CTA */}
        <div className="flex flex-col gap-3 p-4 md:col-span-1">
          <div className="relative aspect-[4/3] w-full overflow-hidden rounded-lg bg-muted">
            {photoUrl ? (
              <>
                <Image
                  src={photoUrl}
                  alt={shop.name}
                  fill
                  className="object-cover"
                  sizes="(max-width: 768px) 100vw, 25vw"
                  unoptimized
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/45 via-transparent to-transparent" />
              </>
            ) : (
              <div className="flex h-full items-center justify-center">
                <Utensils className="h-8 w-8 text-muted-foreground" />
              </div>
            )}
          </div>

          <div className="space-y-1 text-xs text-muted-foreground">
            {(shop.district || shop.mrt_station) && (
              <div className="flex items-center gap-1">
                <MapPin className="h-3 w-3 shrink-0" />
                <span>
                  {shop.district ?? ""}
                  {shop.mrt_station ? ` 捷運${shop.mrt_station}` : ""}
                </span>
              </div>
            )}
            {shop.price_per_person && (
              <div className="flex items-center gap-1">
                <DollarSign className="h-3 w-3 shrink-0" />
                {shop.price_per_person}
              </div>
            )}
            {shop.booking_difficulty && (
              <div className="flex items-center gap-1">
                <CalendarDays className="h-3 w-3 shrink-0" />
                {shop.booking_difficulty}
              </div>
            )}
          </div>

          <Link href={`/shops/${shop.shop_id}`} className="mt-auto block">
            <span className="block w-full rounded-lg bg-[var(--bb-forest)] px-3 py-1.5 text-center text-xs font-medium text-white transition hover:bg-emerald-900">
              查看詳情 / 訂位
            </span>
          </Link>
        </div>

        {/* Middle: review carousel */}
        <div className="p-4 md:col-span-2">
          <div className="mb-2 text-xs font-medium text-muted-foreground">推薦亮點評論</div>
          <ReviewCarousel shopId={shop.shop_id} />
        </div>

        {/* Right: Google Maps iframe */}
        <div className="min-h-[180px] overflow-hidden md:col-span-1">
          <iframe
            src={mapsUrl}
            className="h-full min-h-[180px] w-full border-0"
            loading="lazy"
            referrerPolicy="no-referrer-when-downgrade"
            title={`${shop.name} 地圖`}
          />
        </div>
      </div>

      {/* Positive highlights */}
      <div className="px-4 pb-4">
        <PositiveHighlights shopId={shop.shop_id} />
      </div>
    </div>
  );
}
