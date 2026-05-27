import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, DollarSign, MapPin, MessageSquare, Star } from "lucide-react";
import { Button } from "@/components/ui/button";
import { BookingButton } from "@/components/BookingButton";
import { ShopDetailTabs } from "@/components/ShopDetailTabs";
import { javaApi, type Shop, type ShopAiMetadata, type VoucherOffer } from "@/lib/api";
import { proxyImageUrl } from "@/lib/photoProxy";
import { getBestShopCardPhoto, getShopGalleryPhotos, getShopOverview } from "@/lib/shopPhotoManifest";
import { getShopReviewInsights } from "@/lib/reviewInsights";
import { getSlugByTypeId, getStyleByTypeId } from "@/lib/categoryStyle";
import { isLegacySeedShop } from "@/lib/legacySeedShops";
import { getSimilarShops } from "@/lib/similarShops";

type SimilarShopCard = {
  shopId: number;
  name: string;
  district?: string;
  score?: number;
  avgPrice?: number;
  reason: string;
  photoUrl?: string | null;
};

function parseTags(raw?: string) {
  if (!raw) return [];
  try {
    return typeof raw === "string" ? JSON.parse(raw) : raw;
  } catch {
    return [];
  }
}

function cleanSentence(text?: string | null) {
  return (text ?? "").replace(/\s+/g, " ").trim();
}

function ensurePeriod(text: string) {
  if (!text) return text;
  return /[。！？!]$/.test(text) ? text : `${text}。`;
}

function hasValue(text?: string | null) {
  const cleaned = cleanSentence(text);
  return Boolean(cleaned && cleaned !== "未提及");
}

function isUsableAiIntro(text?: string | null) {
  const cleaned = cleanSentence(text);
  if (!cleaned || cleaned.length < 140) return false;
  const banned = [
    "評論裡最常被提到",
    "被提到的次數通常最高",
    "實際好評常會直接提到",
    "實際評論裡",
    "常見的正面描述",
    "若你在找",
    "人均消費大致落在",
    "訂位難度屬於",
    "預約困難",
  ];
  return !banned.some((phrase) => cleaned.includes(phrase));
}

function formatUpdatedAt(value?: string | null) {
  if (!value) return null;
  return value.slice(0, 16).replace("T", " ");
}

function trimReviewSentence(text?: string | null, limit = 84) {
  const cleaned = cleanSentence(text);
  if (!cleaned) return "";
  const stripped = cleaned
    .replace(/^(主打|評論裡常提到|最多人提到)/, "")
    .replace(/[。！？!]+$/g, "");
  if (stripped.length <= limit) return stripped;
  const clipped = stripped.slice(0, limit);
  const cut = Math.max(clipped.lastIndexOf("，"), clipped.lastIndexOf("、"), clipped.lastIndexOf("。"));
  return (cut > 24 ? clipped.slice(0, cut) : clipped).replace(/[，、。]+$/g, "");
}

function compressAdvice(detail?: string | null, limit = 54) {
  const cleaned = cleanSentence(detail);
  if (!cleaned) return "";
  const simplified = cleaned
    .replace(/^有賓客反映/, "")
    .replace(/^部分賓客提及/, "")
    .replace(/^少數評論提到/, "")
    .replace(/，建議.*$/, "")
    .replace(/，若能.*$/, "")
    .replace(/[。！？!]+$/g, "");
  if (simplified.length <= limit) return simplified;
  const clipped = simplified.slice(0, limit);
  const cut = Math.max(clipped.lastIndexOf("，"), clipped.lastIndexOf("、"));
  return (cut > 18 ? clipped.slice(0, cut) : clipped).replace(/[，、。]+$/g, "");
}

function summarizeReviewTone(text?: string | null) {
  const cleaned = cleanSentence(text).toLowerCase();
  if (!cleaned) return null;
  const tones: string[] = [];
  if (/鮮|清爽|甘甜|甜|濃郁|香|湯頭|暖/.test(cleaned)) tones.push("味道層次鮮明");
  if (/嫩|酥|脆|q|彈|滑/.test(cleaned)) tones.push("口感做得有記憶點");
  if (/服務|親切|專業|桌邊|細心/.test(cleaned)) tones.push("服務節奏穩定");
  if (/環境|裝潢|氣氛|包廂|景觀|寬敞/.test(cleaned)) tones.push("空間氛圍被反覆提起");
  return tones.length ? [...new Set(tones)].slice(0, 2) : null;
}

function parseBusinessHours(value?: string | null): string[] {
  if (!value) return [];
  const trimmed = value.trim();
  if (!trimmed) return [];
  if (trimmed.startsWith("[")) {
    try {
      const parsed = JSON.parse(trimmed);
      if (Array.isArray(parsed)) {
        return parsed.map((item) => String(item).trim()).filter(Boolean);
      }
    } catch {
      // ignore
    }
  }
  return trimmed
    .split(/\n+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function buildIntroText({
  shop,
  ai,
  styleLabel,
  dishes,
  reviewInsights,
}: {
  shop: Shop;
  ai: ShopAiMetadata | null;
  styleLabel: string;
  dishes: string[];
  reviewInsights:
    | {
        advice: { label: string; detail: string }[];
        selectedReviews: { labels: string[]; text: string; rating: number }[];
      }
    | null;
}) {
  const parts: string[] = [];
  const summary = cleanSentence(ai?.aiSummary);
  const highlight = trimReviewSentence(ai?.highlightReview, 72);
  const district = shop.district ?? shop.area ?? "台北市";
  const selectedReviews = reviewInsights?.selectedReviews ?? [];
  const topAdvice = compressAdvice(reviewInsights?.advice?.[0]?.detail, 42);
  const dishLine = dishes.length > 0 ? dishes.slice(0, 4).join("、") : "";
  const positiveReviews = selectedReviews
    .filter((review) => review.rating >= 4)
    .map((review) => summarizeReviewTone(review.text))
    .filter(Boolean)
    .flat()
    .slice(0, 2);
  const lowReviews = selectedReviews
    .filter((review) => review.rating > 0 && review.rating <= 3)
    .map((review) => trimReviewSentence(review.text, 52))
    .filter(Boolean)
    .slice(0, 1);
  const openingStyle = shop.id % 3;

  if (isUsableAiIntro(summary)) {
    if (summary.length <= 300) return ensurePeriod(summary);
    const clipped = summary.slice(0, 300);
    const lastPunct = Math.max(clipped.lastIndexOf("。"), clipped.lastIndexOf("！"), clipped.lastIndexOf("？"));
    return ensurePeriod(lastPunct > 160 ? clipped.slice(0, lastPunct + 1) : clipped);
  }

  if (openingStyle === 0 && summary) {
    parts.push(ensurePeriod(summary));
  } else if (openingStyle === 1) {
    parts.push(`${shop.name}在${district}一帶屬於很容易被拿來安排聚餐或專程前往的一家店，整體風格不是趕時間的快吃型，而是從空間、出餐節奏到主打菜色，都帶著比較完整的用餐儀式感。`);
  } else if (openingStyle === 2) {
    parts.push(`${shop.name}的吸引力，多半不只在店名本身，而是在你坐下來之後會感受到整體節奏被拉穩：空間氛圍、主打料理與服務方式，都更像一頓值得慢慢吃完的正餐。`);
  } else if (summary) {
    parts.push(ensurePeriod(summary));
  } else {
    parts.push(
      `${shop.name}位在${district}，以${styleLabel}為主軸，整體不是匆忙吃完就走的類型，而是更適合坐下來慢慢感受菜色與節奏的一餐。`,
    );
  }

  if (highlight && !summary.includes(highlight)) {
    parts.push(`不少人最後記住的，通常不是單一噱頭，而是像${highlight}這類在整頓飯裡會反覆出現、也最能代表店家性格的細節。`);
  }

  if (dishLine) {
    parts.push(`若是第一次造訪，通常可以先從${dishLine}這幾道開始；它們不只是點單率高，也最能把這家店的招牌方向、口感層次與記憶點交代清楚。`);
  }

  if (positiveReviews.length > 0) {
    parts.push(`整體好評多半會集中在${[...new Set(positiveReviews)].join("、")}，所以它讓人留下印象的，往往不只是名氣，而是菜色與現場體感都有撐住期待。`);
  }

  if (topAdvice) {
    parts.push(`少數意見則會提到${topAdvice}，也就是說它並不是完全沒有挑剔聲音，但討論焦點多半仍圍繞在個別細節，而不是整體失準。`);
  } else if (lowReviews.length > 0) {
    parts.push(`少數意見則會提到「${lowReviews[0]}」，所以若你特別在意細節體感，還是值得先把這些聲音一起看進去。`);
  }

  const text = parts.join("");
  if (text.length >= 200 && text.length <= 320) return text;
  if (text.length < 200) {
    return `${text}${shop.address ? `它位在${district}一帶，` : ""}如果你想找的是一間不只菜色有記憶點，連服務、環境或整體節奏也會被客人反覆拿出來討論的店，這家通常會比單純高分名單更值得細看。}`;
  }

  const clipped = text.slice(0, 300);
  const lastPunct = Math.max(clipped.lastIndexOf("。"), clipped.lastIndexOf("！"), clipped.lastIndexOf("？"));
  return lastPunct > 180 ? clipped.slice(0, lastPunct + 1) : `${clipped}...`;
}

function toFallbackSimilarCards(items: Awaited<ReturnType<typeof getSimilarShops>>): SimilarShopCard[] {
  return items.map((item) => ({
    shopId: item.shopId,
    name: item.name,
    district: item.district,
    score: undefined,
    avgPrice: undefined,
    reason: item.reason,
    photoUrl: proxyImageUrl(getBestShopCardPhoto(item.shopId)),
  }));
}

function buildCategorySimilarCards(baseShop: Shop, candidates: Shop[]): SimilarShopCard[] {
  return candidates
    .filter((candidate) => candidate.id !== baseShop.id && !isLegacySeedShop(candidate.id))
    .map((candidate) => {
      const sameDistrict = Boolean(baseShop.district && candidate.district === baseShop.district);
      const sameMrt = Boolean(baseShop.mrtStation && candidate.mrtStation === baseShop.mrtStation);
      const areaClose = Boolean(baseShop.area && candidate.area === baseShop.area);

      let reason = "同類型口袋名單";
      if (sameDistrict) reason = `同類型・${candidate.district}`;
      else if (sameMrt) reason = `同類型・${candidate.mrtStation}`;
      else if (areaClose) reason = `同類型・${candidate.area}`;
      else if (candidate.district) reason = `同類型・${candidate.district}`;

      return {
        shopId: candidate.id,
        name: candidate.name,
        district: candidate.district ?? candidate.area,
        score: candidate.score,
        avgPrice: candidate.avgPrice,
        reason,
        photoUrl: proxyImageUrl(getBestShopCardPhoto(candidate.id)),
        sortKey: [
          sameDistrict ? 1 : 0,
          sameMrt ? 1 : 0,
          areaClose ? 1 : 0,
          candidate.score ?? 0,
          candidate.comments ?? 0,
        ],
      };
    })
    .sort((a, b) => {
      for (let i = 0; i < a.sortKey.length; i += 1) {
        const diff = b.sortKey[i]! - a.sortKey[i]!;
        if (diff !== 0) return diff;
      }
      return a.name.localeCompare(b.name, "zh-Hant");
    })
    .slice(0, 4)
    .map(({ sortKey: _sortKey, ...item }) => item);
}

export default async function ShopDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const shopId = Number(id);

  const [shopRes, aiRes, voucherRes, hotSeatRes, reviewInsights, fallbackSimilar, photoUrls] = await Promise.all([
    javaApi.shopDetail(shopId).catch(() => null),
    javaApi.shopAiMetadata(id).catch(() => ({ success: false, data: null })),
    javaApi.shopVouchers(shopId).catch(() => ({ success: false, data: [] as VoucherOffer[] })),
    javaApi.hotSeatVouchers(shopId).catch(() => ({ success: false, data: [] as { id: number; stock: number }[] })),
    getShopReviewInsights(shopId).catch(() => null),
    getSimilarShops(shopId).catch(() => []),
    Promise.resolve(getShopGalleryPhotos(shopId)),
  ]);

  const shop = shopRes?.data;
  if (!shop) return notFound();

  const ai: ShopAiMetadata | null = aiRes?.data ?? null;
  const vouchers = (voucherRes?.data ?? []) as VoucherOffer[];
  const style = getStyleByTypeId(shop.typeId);
  const Icon = style.icon;
  const dishes = parseTags(ai?.signatureDishes);
  const tags = parseTags(ai?.atmosphereTags);
  const introText = buildIntroText({ shop, ai, styleLabel: style.label, dishes, reviewInsights });
  const lastUpdated = formatUpdatedAt(ai?.extractedAt);
  const businessHours = parseBusinessHours(shop.businessHours ?? ai?.openingHours);

  const categorySlug = getSlugByTypeId(shop.typeId);
  const sameCategoryRes = categorySlug
    ? await javaApi.shopsByCategory(categorySlug, 1, 18).catch(() => null)
    : null;
  const categorySimilar = buildCategorySimilarCards(shop, sameCategoryRes?.data ?? []);
  const similarShops =
    categorySimilar.length > 0 ? categorySimilar : toFallbackSimilarCards(fallbackSimilar).slice(0, 4);

  const hotSeatStockMap = new Map(
    (hotSeatRes?.data ?? []).map((offer) => [offer.id, offer.stock]),
  );
  const overview = getShopOverview(shopId);
  const proxiedPhotoUrls = photoUrls.map((url) => proxyImageUrl(url)).filter(Boolean) as string[];
  const fallbackImage = shop.images?.startsWith("http") ? shop.images : null;
  const coverPhoto = proxyImageUrl(getBestShopCardPhoto(shopId, fallbackImage)) ?? proxiedPhotoUrls[0] ?? null;
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
          body: `這家店目前有熱門時段限量名額，剩 ${stock} 席，先鎖位通常比現場碰運氣更穩。`,
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

  const reviewInsightCards = [
    overview?.price_overview ? { label: "Google 平均每人", value: overview.price_overview } : null,
    hasValue(ai?.bookingDifficulty) ? { label: "預約難度", value: ai!.bookingDifficulty! } : null,
    hasValue(ai?.pricePerPerson) ? { label: "參考價位", value: ai!.pricePerPerson! } : null,
    dishes.length > 0 ? { label: "最常被提到", value: dishes.slice(0, 3).join("、") } : null,
    tags.length > 0 ? { label: "常見場景", value: tags.slice(0, 3).join("、") } : null,
  ].filter(Boolean) as { label: string; value: string }[];

  return (
    <div className="min-h-screen pb-32">
      <div className="max-w-4xl mx-auto px-4 md:px-8 pt-6">
        <Link href="/shops">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="h-4 w-4 mr-1" />
            返回
          </Button>
        </Link>
      </div>

      <section className="max-w-4xl mx-auto px-4 md:px-8 mt-4">
        <div className={`relative overflow-hidden bg-gradient-to-br ${style.gradient} rounded-2xl min-h-[320px] md:min-h-[360px] p-6 md:p-10`}>
          {coverPhoto ? (
            <>
              <img
                src={coverPhoto}
                alt={`${shop.name}-cover`}
                className="absolute inset-0 h-full w-full object-cover"
              />
              <div className="absolute inset-0 bg-gradient-to-r from-black/65 via-black/35 to-black/10" />
            </>
          ) : null}
          <div className="relative flex h-full items-start gap-4 md:items-end">
            <div className="hidden md:flex h-16 w-16 rounded-xl bg-background/60 backdrop-blur items-center justify-center shrink-0">
              <Icon className="h-8 w-8 text-foreground/60" strokeWidth={1.5} />
            </div>
            <div className="flex-1">
              <div className="flex flex-wrap gap-2 mb-2">
                <span className="text-xs px-2 py-0.5 rounded-full bg-background/60 backdrop-blur">
                  {style.label}
                </span>
                {shop.district ? (
                  <span className="text-xs px-2 py-0.5 rounded-full bg-background/60 backdrop-blur">
                    📍 {shop.district}
                  </span>
                ) : null}
              </div>
              <h1 className={`text-2xl md:text-4xl font-bold tracking-tight ${coverPhoto ? "text-white" : ""}`}>{shop.name}</h1>
              {shop.address ? (
                <p className={`text-sm mt-2 ${coverPhoto ? "text-white/85" : "text-foreground/70"}`}>{shop.address}</p>
              ) : null}
            </div>
          </div>
        </div>
      </section>

      <section className="max-w-4xl mx-auto px-4 md:px-8 mt-6">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="rounded-xl border p-4">
            <div className="flex items-center gap-2 text-muted-foreground text-xs mb-1">
              <Star className="h-3.5 w-3.5" />
              評分
            </div>
            <div className="font-mono text-2xl font-bold">
              {shop.score ? (shop.score / 10).toFixed(1) : "—"}
            </div>
          </div>
          <div className="rounded-xl border p-4">
            <div className="flex items-center gap-2 text-muted-foreground text-xs mb-1">
              <MessageSquare className="h-3.5 w-3.5" />
              評論數
            </div>
            <div className="font-mono text-2xl font-bold">
              {shop.comments?.toLocaleString() ?? "—"}
            </div>
          </div>
          <div className="rounded-xl border p-4">
            <div className="flex items-center gap-2 text-muted-foreground text-xs mb-1">
              <DollarSign className="h-3.5 w-3.5" />
              平均消費
            </div>
            <div className="font-mono text-2xl font-bold">
              {overview?.price_overview ?? (shop.avgPrice ? `$${shop.avgPrice}` : ai?.pricePerPerson ?? "—")}
            </div>
          </div>
          <div className="rounded-xl border p-4">
            <div className="flex items-center gap-2 text-muted-foreground text-xs mb-1">
              <MapPin className="h-3.5 w-3.5" />
              區域
            </div>
            <div className="text-2xl font-bold">
              {shop.district ?? shop.area ?? "—"}
            </div>
          </div>
        </div>
      </section>

      {(hotSeatOffers.length > 0 || merchantOffers.length > 0) && (
        <section id="offers" className="max-w-4xl mx-auto px-4 md:px-8 mt-6 space-y-6">
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

          {hotSeatOffers.length > 0 ? (
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
          ) : null}

          {merchantOffers.length > 0 ? (
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
          ) : null}
        </section>
      )}

      <ShopDetailTabs
        introText={introText}
        address={shop.address}
        businessHours={businessHours}
        phone={ai?.phone}
        bookingDifficulty={hasValue(ai?.bookingDifficulty) ? ai?.bookingDifficulty : undefined}
        pricePerPerson={hasValue(ai?.pricePerPerson) ? ai?.pricePerPerson : undefined}
        priceOverview={overview?.price_overview}
        priceReportCount={overview?.price_report_count}
        priceBuckets={Array.isArray(overview?.price_buckets) ? overview?.price_buckets as { label: string; count?: number; share?: number }[] : undefined}
        popularTime={overview?.popular_time ?? null}
        visitDuration={overview?.visit_duration ?? null}
        dishes={dishes}
        tags={tags}
        reviewInsightCards={reviewInsightCards}
        advice={reviewInsights?.advice ?? []}
        selectedReviews={reviewInsights?.selectedReviews ?? []}
        reviewTotal={reviewInsights?.totalReviews ?? 0}
        reviewNonEmpty={reviewInsights?.nonEmptyReviews ?? 0}
        photoUrls={proxiedPhotoUrls}
        photoFallbackLabel={shop.name}
        similarShops={similarShops}
        mapQuery={`${shop.name} ${shop.address ?? ""}`}
        lastUpdated={lastUpdated}
      />

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
