"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { ChevronLeft, ChevronRight, MapPin, Star } from "lucide-react";
import type { ShopReviewInsights } from "@/lib/reviewInsights";
import { getBestShopCardPhoto } from "@/lib/shopPhotoManifest";
import { proxyImageUrl } from "@/lib/photoProxy";

export type AgentShop = {
  shop_id: number;
  name: string;
  district?: string | null;
  mrt_station?: string | null;
  avg_price?: number | null;
  price_per_person?: string | null;
  booking_difficulty?: string | null;
  atmosphere_tags?: string[] | null;
  signature_dishes?: string[] | null;
  ai_summary?: string | null;
  hot_seat_vouchers?: { id: number; title: string }[] | null;
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

  if (loading) {
    return (
      <div className="flex flex-col gap-2 animate-pulse">
        <div className="h-3 w-16 rounded bg-muted" />
        <div className="h-16 w-full rounded bg-muted" />
        <div className="h-3 w-24 rounded bg-muted" />
      </div>
    );
  }

  const reviews = insights?.selectedReviews.slice(0, 3) ?? [];
  if (!reviews.length) {
    return <p className="text-xs text-muted-foreground">暫無評論資料</p>;
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
    <div data-testid="agent-shop-card" className="overflow-hidden rounded-2xl border bg-background shadow-sm">
      {/* Header row: rank + name + hot seat badge */}
      <div className="flex items-center gap-2 border-b px-4 py-2.5">
        <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground">
          {rank}
        </span>
        <span className="font-semibold">{shop.name}</span>
        {hasHotSeat && (
          <span className="ml-auto rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-800">
            🔥 Hot Seat 可搶
          </span>
        )}
      </div>

      {/* Three-column grid */}
      <div className="grid grid-cols-1 divide-y md:grid-cols-4 md:divide-x md:divide-y-0">
        {/* Left: photo + meta + CTA */}
        <div className="flex flex-col gap-3 p-4 md:col-span-1">
          <div className="relative aspect-[4/3] w-full overflow-hidden rounded-lg bg-muted">
            {photoUrl ? (
              <Image
                src={photoUrl}
                alt={shop.name}
                fill
                className="object-cover"
                sizes="(max-width: 768px) 100vw, 25vw"
                unoptimized
              />
            ) : (
              <div className="flex h-full items-center justify-center text-4xl">🍽️</div>
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
            {shop.price_per_person && <div>💰 {shop.price_per_person}</div>}
            {shop.booking_difficulty && <div>📅 {shop.booking_difficulty}</div>}
          </div>

          <Link href={`/shops/${shop.shop_id}`} className="mt-auto block">
            <span className="block w-full rounded-lg bg-primary px-3 py-1.5 text-center text-xs font-medium text-primary-foreground transition hover:bg-primary/90">
              查看詳情 / 訂位
            </span>
          </Link>
        </div>

        {/* Middle: review carousel */}
        <div className="p-4 md:col-span-2">
          <div className="mb-2 text-xs font-medium text-muted-foreground">精選評論</div>
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

    </div>
  );
}
