"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { AgentShop } from "@/lib/agentTypes";
import type { AgentComparisonRow } from "@/lib/agentStream";

type TableReviewInsights = {
  selectedReviews?: {
    rating?: number;
    text?: string;
    labels?: string[];
  }[];
  totalReviews?: number;
  nonEmptyReviews?: number;
};

function shopRaw(shop: AgentShop) {
  return shop as unknown as {
    category?: string | null;
    comments?: number | null;
    distance?: number | null;
  };
}

function cleanComparisonText(value?: string | null): string {
  return (value ?? "").replace(/\s+/g, " ").trim();
}

function shortComparisonText(value: string, limit = 58): string {
  const cleaned = cleanComparisonText(value).replace(/[。！？!]+$/g, "");
  if (cleaned.length <= limit) return cleaned;
  const clipped = cleaned.slice(0, limit);
  const cut = Math.max(clipped.lastIndexOf("，"), clipped.lastIndexOf("、"), clipped.lastIndexOf("；"));
  return `${(cut > 18 ? clipped.slice(0, cut) : clipped).replace(/[，、；]+$/g, "")}...`;
}

function usefulReviews(insights?: TableReviewInsights | null) {
  return (insights?.selectedReviews ?? [])
    .filter((review) => (review.rating ?? 0) >= 4 && cleanComparisonText(review.text))
    .slice(0, 3);
}

function hasRichComparisonData(shop: AgentShop, insights?: TableReviewInsights | null): boolean {
  return Boolean(
    cleanComparisonText(shop.ai_summary) ||
      (shop.signature_dishes?.length ?? 0) > 0 ||
      (shop.atmosphere_tags?.length ?? 0) > 0 ||
      usefulReviews(insights).length > 0,
  );
}

function formatFeatureHighlight(shop: AgentShop, insights?: TableReviewInsights | null): string {
  const dishes = (shop.signature_dishes ?? []).filter(Boolean).slice(0, 3);
  if (dishes.length > 0) return `招牌：${dishes.join("、")}`;

  const reviews = usefulReviews(insights);
  const labelCounts = new Map<string, number>();
  for (const review of reviews) {
    for (const label of review.labels ?? []) {
      if (["訂位", "上菜"].includes(label)) continue;
      labelCounts.set(label, (labelCounts.get(label) ?? 0) + 1);
    }
  }
  const labels = [...labelCounts.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([label]) => label)
    .slice(0, 2);
  if (labels.length > 0) return `評論亮點：${labels.join("、")}`;

  const reviewText = cleanComparisonText(reviews[0]?.text);
  if (reviewText) return shortComparisonText(reviewText);

  const summary = cleanComparisonText(shop.ai_summary);
  if (summary) return shortComparisonText(summary);

  const raw = shopRaw(shop);
  if ((raw.comments ?? 0) >= 500) return `Google 評論量 ${raw.comments} 則，可先作為人氣參考`;
  return "資料較少：目前只有基本店名、地點與價位，建議先看 Google Maps 或電話確認";
}

function formatBestFor(shop: AgentShop, insights?: TableReviewInsights | null): string {
  const tags = (shop.atmosphere_tags ?? []).filter(Boolean).slice(0, 2);
  if (tags.length > 0) return tags.join("、");

  const text = [
    shop.name,
    shopRaw(shop).category,
    shop.ai_summary,
    ...usefulReviews(insights).map((review) => review.text ?? ""),
  ]
    .join(" ")
    .toLowerCase();

  if (/火鍋|麻辣|鍋底|鴛鴦鍋/.test(text)) return "多人聚餐、想吃鍋物";
  if (/漢堡|burger|美式/.test(text)) return "朋友聚餐、想吃美式漢堡";
  if (/牛肉麵|麵|小吃/.test(text)) return "快速午晚餐、一人用餐";
  if (/家庭|長輩|親子|小孩/.test(text)) return "家庭聚餐、長輩同行";
  if (/商務|包廂|正式|宴客/.test(text)) return "商務聚餐、正式宴客";
  if (/約會|氣氛|浪漫|安靜/.test(text)) return "約會、安靜聊天";
  if ((shop.avg_price ?? 0) <= 300) return "快速簡餐、預算友善";
  return hasRichComparisonData(shop, insights) ? "朋友聚餐、一般正餐" : "需先確認資料完整度";
}

function formatOnlineBookingStatus(shop: AgentShop, insights?: TableReviewInsights | null): string {
  if ((shop.hot_seat_vouchers?.length ?? 0) > 0) return "限時餐券可搶";
  if (!hasRichComparisonData(shop, insights)) return "可線上訂位，但資料較少";
  const booking = shop.booking_difficulty ?? "";
  if (booking.includes("預約困難")) return "可線上訂位，建議提前";
  if (booking.includes("現場可入")) return "可線上訂位；通常也可現場";
  if (booking.includes("未提及")) return "可線上訂位，建議確認";
  return booking || "可線上訂位";
}

function formatComparisonMeta(shop: AgentShop): string {
  const raw = shop as unknown as {
    distance?: number | null;
  };
  const price = shop.price_per_person ?? (shop.avg_price != null ? `NT$ ${shop.avg_price}` : "");
  const location = [
    shop.district,
    shop.mrt_station ? `捷運${shop.mrt_station}` : null,
    raw.distance != null ? `${Math.round(raw.distance)}m` : null,
  ]
    .filter(Boolean)
    .join(" · ");
  return [price, location].filter(Boolean).join(" · ");
}

export function AgentShopComparisonTable({ shops, rows }: { shops: AgentShop[]; rows?: AgentComparisonRow[] }) {
  const [insightsByShop, setInsightsByShop] = useState<Record<number, TableReviewInsights | null>>({});
  const shopIdsKey = shops.map((shop) => shop.shop_id).join(",");
  const rowsByShop = new Map((rows ?? []).map((row) => [Number(row.shop_id), row]));

  useEffect(() => {
    if (!shopIdsKey) return;
    let canceled = false;
    const ids = shopIdsKey
      .split(",")
      .map((id) => Number(id))
      .filter((id) => Number.isFinite(id));

    Promise.all(
      ids.map(async (id) => {
        try {
          const response = await fetch(`/api/shop/${id}/reviews`);
          if (!response.ok) return [id, null] as const;
          return [id, (await response.json()) as TableReviewInsights] as const;
        } catch {
          return [id, null] as const;
        }
      }),
    ).then((entries) => {
      if (canceled) return;
      setInsightsByShop(Object.fromEntries(entries));
    });

    return () => {
      canceled = true;
    };
  }, [shopIdsKey]);

  if (shops.length < 2) return null;
  return (
    <section className="overflow-hidden rounded-xl border border-black/10 bg-white/90 shadow-sm">
      <div className="border-b border-black/10 px-4 py-3">
        <h3 className="text-sm font-black text-zinc-900">快速比較</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-[980px] table-fixed text-left text-sm">
          <thead className="bg-zinc-50 text-xs font-black text-zinc-500">
            <tr>
              <th className="w-[22%] px-4 py-3">店名</th>
              <th className="w-[34%] px-4 py-3">特色亮點</th>
              <th className="w-[22%] px-4 py-3">適合情境</th>
              <th className="w-[22%] px-4 py-3">是否可線上訂位</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-black/5">
            {shops.map((shop) => {
              const insights = insightsByShop[shop.shop_id];
              const backendRow = rowsByShop.get(shop.shop_id);
              const isThin = !hasRichComparisonData(shop, insights);
              const meta = backendRow?.meta || formatComparisonMeta(shop);
              return (
                <tr key={shop.shop_id} className="align-top">
                  <td className="px-4 py-3">
                    <Link href={`/shops/${shop.shop_id}`} className="font-bold text-zinc-900 hover:text-emerald-800">
                      {shop.name}
                    </Link>
                    {meta ? <div className="mt-1 text-xs leading-5 text-zinc-500">{meta}</div> : null}
                  </td>
                  <td className={`px-4 py-3 leading-6 ${isThin ? "text-amber-800" : "text-zinc-700"}`}>
                    {backendRow?.feature_highlight || formatFeatureHighlight(shop, insights)}
                  </td>
                  <td className="px-4 py-3 leading-6 text-zinc-700">{backendRow?.best_for || formatBestFor(shop, insights)}</td>
                  <td className="px-4 py-3 leading-6 text-zinc-700">{backendRow?.booking_status || formatOnlineBookingStatus(shop, insights)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
