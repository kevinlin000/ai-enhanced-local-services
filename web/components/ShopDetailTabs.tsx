"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { Clock3, ExternalLink, MapPinned, PhoneCall } from "lucide-react";

type SimilarShopCard = {
  shopId: number;
  name: string;
  district?: string;
  score?: number;
  avgPrice?: number;
  reason: string;
  photoUrl?: string | null;
};

type ReviewSnippet = {
  author: string;
  rating: number;
  text: string;
  publishTime?: string | null;
  labels: string[];
};

type AdviceInsight = {
  label: string;
  detail: string;
};

type Props = {
  introText: string;
  address?: string;
  businessHours?: string[];
  phone?: string;
  bookingDifficulty?: string;
  pricePerPerson?: string;
  dishes: string[];
  tags: string[];
  reviewInsightCards: { label: string; value: string }[];
  advice: AdviceInsight[];
  selectedReviews: ReviewSnippet[];
  reviewTotal: number;
  reviewNonEmpty: number;
  photoUrls: string[];
  photoFallbackLabel: string;
  similarShops: SimilarShopCard[];
  mapQuery: string;
  lastUpdated?: string | null;
};

type TabKey = "overview" | "gallery" | "reviews";

function ExpandableText({
  text,
  limit = 220,
  className = "",
}: {
  text: string;
  limit?: number;
  className?: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const shouldCollapse = text.length > limit;
  const visible = !shouldCollapse || expanded ? text : `${text.slice(0, limit)}...`;

  return (
    <div className={className}>
      <p className="whitespace-pre-line leading-relaxed text-foreground/85">{visible}</p>
      {shouldCollapse ? (
        <button
          type="button"
          onClick={() => setExpanded((value) => !value)}
          className="mt-2 text-sm font-medium text-muted-foreground hover:text-foreground"
        >
          {expanded ? "收回" : "更多"}
        </button>
      ) : null}
    </div>
  );
}

export function ShopDetailTabs(props: Props) {
  const [activeTab, setActiveTab] = useState<TabKey>("overview");

  const firstPhoto = props.photoUrls[0] ?? null;
  const restPhotos = props.photoUrls.slice(1, 6);
  const mapsHref = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(props.mapQuery)}`;
  const menuHref = mapsHref;
  const telHref = props.phone ? `tel:${props.phone.replace(/[^\d+]/g, "")}` : null;

  const tabs = useMemo(
    () => [
      { key: "overview" as const, label: "餐廳介紹" },
      { key: "gallery" as const, label: "菜單/照片" },
      { key: "reviews" as const, label: "評論" },
    ],
    [],
  );

  return (
    <section className="max-w-4xl mx-auto px-4 md:px-8 mt-6">
      <div className="border-b">
        <div className="flex flex-wrap gap-6 text-base">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              type="button"
              onClick={() => setActiveTab(tab.key)}
              className={`pb-3 pt-1 border-b-2 transition-colors ${
                activeTab === tab.key
                  ? "border-foreground font-semibold text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {activeTab === "overview" ? (
        <div className="space-y-8 pt-6">
          <div className="rounded-2xl border bg-background p-5">
            <ExpandableText text={props.introText} limit={260} />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {props.reviewInsightCards.map((card) => (
              <div key={card.label} className="rounded-2xl border bg-background p-5">
                <div className="text-xs text-muted-foreground">{card.label}</div>
                <div className="mt-2 text-base font-medium leading-relaxed">{card.value}</div>
              </div>
            ))}
          </div>

          {(props.address || props.phone || props.businessHours) && (
            <div className="space-y-3">
              <h3 className="text-lg font-semibold">基本資訊</h3>
              <div className="rounded-2xl border overflow-hidden">
                <iframe
                  src={`https://maps.google.com/maps?q=${encodeURIComponent(props.mapQuery)}&z=16&output=embed`}
                  width="100%"
                  height="280"
                  style={{ border: 0 }}
                  loading="lazy"
                  referrerPolicy="no-referrer-when-downgrade"
                />
              </div>

              <div className="rounded-2xl border bg-background divide-y">
                {props.address ? (
                  <a
                    href={mapsHref}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-start gap-3 px-4 py-4 text-sm leading-relaxed hover:bg-muted/40"
                  >
                    <MapPinned className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                    <span className="flex-1 underline-offset-2 hover:underline">{props.address}</span>
                    <ExternalLink className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                  </a>
                ) : null}
                {props.phone && telHref ? (
                  <a
                    href={telHref}
                    className="flex items-start gap-3 px-4 py-4 text-sm hover:bg-muted/40"
                  >
                    <PhoneCall className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                    <span className="underline-offset-2 hover:underline">{props.phone}</span>
                  </a>
                ) : null}
                {props.businessHours?.length ? (
                  <div className="flex items-start gap-3 px-4 py-4 text-sm">
                    <Clock3 className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                    <div className="space-y-1">
                      {props.businessHours.map((line) => (
                        <div key={line}>{line}</div>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
          )}

          {props.similarShops.length > 0 ? (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">跟這家店相似的餐廳</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {props.similarShops.map((candidate) => (
                  <Link
                    key={candidate.shopId}
                    href={`/shops/${candidate.shopId}`}
                    className="overflow-hidden rounded-2xl border bg-background hover:border-primary/30 hover:bg-primary/[0.03] transition-colors"
                  >
                    <div className="aspect-[16/9] overflow-hidden bg-muted/20">
                      {candidate.photoUrl ? (
                        <img src={candidate.photoUrl} alt={`${candidate.name}-cover`} className="h-full w-full object-cover" />
                      ) : (
                        <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                          暫無照片
                        </div>
                      )}
                    </div>
                    <div className="p-5">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="font-medium leading-snug">{candidate.name}</div>
                          <div className="mt-1 text-sm text-muted-foreground">
                            {candidate.district ?? "台北市"} · {candidate.avgPrice ? `約 $${candidate.avgPrice}` : "價位待補"}
                          </div>
                          {candidate.score ? (
                            <div className="mt-1 text-sm text-amber-700">★ {(candidate.score / 10).toFixed(1)}</div>
                          ) : null}
                        </div>
                        <span className="rounded-full bg-primary/10 px-2 py-1 text-xs text-primary">
                          {candidate.reason}
                        </span>
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      ) : null}

      {activeTab === "gallery" ? (
        <div className="space-y-8 pt-6">
          <div className="space-y-4">
            <h3 className="text-lg font-semibold">菜單</h3>
            <a
              href={menuHref}
              target="_blank"
              rel="noreferrer"
              className="relative block aspect-[16/7] overflow-hidden rounded-2xl border bg-muted/30"
            >
              {firstPhoto ? (
                <img
                  src={firstPhoto}
                  alt={`${props.photoFallbackLabel}-menu-cover`}
                  className="absolute inset-0 h-full w-full object-cover"
                />
              ) : null}
              <div className="absolute inset-0 bg-gradient-to-r from-black/70 via-black/35 to-black/15" />
              <div className="absolute inset-x-0 bottom-0 px-5 py-6 text-white">
                <div className="text-xl font-semibold">去 Google Maps 看菜單</div>
                <p className="mt-2 text-sm text-white/80">直接開店家頁，若 Google 有收錄菜單、照片或最新營業資訊，會比一般搜尋結果更準。</p>
              </div>
            </a>
          </div>

          <div className="space-y-4">
            <h3 className="text-lg font-semibold">餐廳照片</h3>
            {firstPhoto ? (
              <div className="space-y-4">
                <div className="aspect-[16/9] overflow-hidden rounded-2xl border bg-muted/20">
                  <img src={firstPhoto} alt={props.photoFallbackLabel} className="h-full w-full object-cover" />
                </div>
                {restPhotos.length > 0 ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-start">
                    {restPhotos.map((url, index) => (
                      <div key={`${url}-${index}`} className="aspect-[4/3] overflow-hidden rounded-2xl border bg-muted/20">
                        <img src={url} alt={`${props.photoFallbackLabel}-${index + 2}`} className="h-full w-full object-cover" />
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>
            ) : (
              <div className="rounded-2xl border bg-gradient-to-br from-stone-100 via-amber-50 to-orange-100 p-8">
                <div className="text-xs font-mono text-muted-foreground">PHOTO COVER</div>
                <div className="mt-2 text-2xl font-semibold">{props.photoFallbackLabel}</div>
                <p className="mt-3 max-w-xl text-sm text-muted-foreground leading-relaxed">
                  這家店目前先以展示封面呈現；之後若補進更多實景或菜色照，這裡會優先更新成真實照片。
                </p>
              </div>
            )}
          </div>
        </div>
      ) : null}

      {activeTab === "reviews" ? (
        <div className="space-y-8 pt-6">
          <div className="space-y-4">
            <h3 className="text-lg font-semibold">餐廳特色</h3>
            <div className="overflow-hidden rounded-2xl border">
              <table className="w-full text-sm">
                <thead className="bg-stone-100 text-left">
                  <tr>
                    <th className="px-4 py-3 font-medium text-muted-foreground">類別</th>
                    <th className="px-4 py-3 font-medium text-muted-foreground">重點描述</th>
                  </tr>
                </thead>
                <tbody>
                  {props.reviewInsightCards.slice(0, 4).map((card) => (
                    <tr key={card.label} className="border-t align-top">
                      <td className="px-4 py-4 font-medium">{card.label}</td>
                      <td className="px-4 py-4 text-muted-foreground leading-relaxed">{card.value}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {props.advice.length > 0 ? (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">常見建議</h3>
              <div className="overflow-hidden rounded-2xl border">
                <table className="w-full text-sm">
                  <thead className="bg-stone-100 text-left">
                    <tr>
                      <th className="px-4 py-3 font-medium text-muted-foreground">類別</th>
                      <th className="px-4 py-3 font-medium text-muted-foreground">重點描述</th>
                    </tr>
                  </thead>
                  <tbody>
                    {props.advice.map((item) => (
                      <tr key={item.label} className="border-t align-top">
                        <td className="px-4 py-4 font-medium">{item.label}</td>
                        <td className="px-4 py-4 text-muted-foreground leading-relaxed">{item.detail}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}

          <div className="space-y-4">
            <h3 className="text-lg font-semibold">Google 顧客評論</h3>
            <p className="text-sm text-muted-foreground">
              從 {props.reviewTotal} 則評論中整理，以下先挑 5 則最能幫你判斷菜色、服務、環境與值不值得訂位的內容。
            </p>
            <div className="space-y-4">
              {props.selectedReviews.map((review, index) => (
                <div key={`${review.author}-${index}`} className="rounded-2xl border bg-background p-5">
                  <div className="flex flex-wrap items-center gap-3 text-sm">
                    <span className="font-medium">{review.author}</span>
                    <span className="font-mono text-amber-600">★ {review.rating ? review.rating.toFixed(1) : "—"}</span>
                    {review.publishTime ? (
                      <span className="text-xs text-muted-foreground">{review.publishTime.slice(0, 10)}</span>
                    ) : null}
                  </div>
                  {review.labels.length > 0 ? (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {review.labels.map((label) => (
                        <span key={label} className="rounded-full bg-muted px-2.5 py-1 text-xs text-muted-foreground">
                          {label}
                        </span>
                      ))}
                    </div>
                  ) : null}
                  <ExpandableText text={review.text} limit={180} className="mt-3 text-sm" />
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : null}

      {props.lastUpdated ? (
        <div className="pt-8 text-xs text-muted-foreground">
          資料更新：{props.lastUpdated}
        </div>
      ) : null}
    </section>
  );
}
