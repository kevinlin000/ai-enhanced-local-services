import { getExtractedShop } from "@/lib/extractedShops";
import { getShopManifestReviews } from "@/lib/shopReviews.server";

export type ReviewLanguage = "zh" | "ja" | "ko" | "en";

export type ReviewSnippet = {
  author: string;
  rating: number;
  text: string;
  publishTime?: string | null;
  labels: string[];
  language: ReviewLanguage;
};

export type AdviceInsight = {
  label: string;
  detail: string;
};

export type FeatureInsight = {
  label: string;
  detail: string;
};

export type ShopReviewInsights = {
  selectedReviews: ReviewSnippet[];
  advice: AdviceInsight[];
  totalReviews: number;
  nonEmptyReviews: number;
};

const ADVICE_RULES: { label: string; detail: string; keywords: string[] }[] = [
  {
    label: "上菜節奏",
    detail:
      "部分評論提到客滿時餐點現做會稍微多等一會，若你後面還有行程，或是安排長輩聚餐、慶生聚會，建議多預留一些用餐時間會更從容。",
    keywords: ["上菜", "太慢", "太久", "等待", "節奏", "久等"],
  },
  {
    label: "價格感受",
    detail:
      "部分客人會特別在意單點價位或套餐份量，若你對預算較敏感，建議先確認套餐內容與份量，再決定要單點還是直接選配好的組合。",
    keywords: ["太貴", "價格", "價位", "cp值", "預算", "套餐"],
  },
  {
    label: "調味偏好",
    detail:
      "少數評論會提到個別菜色調味偏重；如果你平常口味偏清淡，點餐時可以先問店員推薦較清爽的選項，體感通常會更穩。",
    keywords: ["太鹹", "偏鹹", "口味重", "重鹹", "油"],
  },
  {
    label: "服務溝通",
    detail:
      "少數評論提到尖峰時段偶爾會有照顧不周或需求漏接的情況，若你有座位、熟度或客製化需求，建議主動再確認一次會更安心。",
    keywords: ["服務", "店員", "態度", "溝通", "推我", "不理"],
  },
  {
    label: "環境噪音",
    detail:
      "用餐尖峰時段通常會比較熱絡，若你偏好安靜聊天或商務型聚會，建議避開熱門時段，或訂位時先詢問是否能安排較邊角的位置。",
    keywords: ["吵", "擁擠", "太擠", "空間", "座位"],
  },
];

const REVIEW_LABEL_RULES: { label: string; keywords: string[] }[] = [
  { label: "服務", keywords: ["服務", "店員", "態度", "桌邊", "親切", "專業"] },
  { label: "環境", keywords: ["環境", "裝潢", "氣氛", "空間", "包廂", "景觀"] },
  { label: "價格", keywords: ["價格", "價位", "套餐", "預算", "划算", "值得", "元", "$"] },
  { label: "訂位", keywords: ["訂位", "預約", "排隊", "候位", "熱門", "難訂"] },
  { label: "上菜", keywords: ["上菜", "節奏", "久等", "等待"] },
  { label: "口感", keywords: ["口感", "湯頭", "香氣", "酥", "嫩", "脆", "鮮"] },
];

function normalizeText(value?: string | null) {
  return (value ?? "").replace(/\s+/g, " ").trim();
}

function hasEnoughChinese(text: string) {
  const cleaned = normalizeText(text);
  if (!cleaned) return false;
  const chineseChars = (cleaned.match(/[一-鿿]/g) ?? []).length;
  return chineseChars >= Math.max(8, Math.floor(cleaned.length * 0.2));
}

function detectLanguage(text: string): ReviewLanguage {
  if (/[぀-ゟ゠-ヿ]/.test(text)) return "ja";
  if (/[가-힯]/.test(text)) return "ko";
  if (hasEnoughChinese(text)) return "zh";
  return "en";
}

function parseList(value?: string[] | string) {
  if (!value) return [];
  if (Array.isArray(value)) return value.filter(Boolean);
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed.filter(Boolean) : [];
  } catch {
    return [];
  }
}

function informativenessScore(text: string): number {
  const len = text.length;
  if (len < 80 || len > 300) return 0;
  let score = 1;
  if (/推薦|必點|招牌|口感|湯頭|服務|環境|氣氛|包廂|上菜|訂位|排隊/.test(text)) score += 2;
  if (/[0-9]+|元|\$|NT\$/.test(text)) score += 1;
  return score;
}

function recencyScore(publishTime?: string | null): number {
  if (!publishTime) return 0;
  const ms = Date.now() - new Date(publishTime).getTime();
  const days = ms / 86400000;
  if (days < 90) return 3;
  if (days < 365) return 2;
  if (days < 730) return 1;
  return 0;
}

// zh=0 sorts first; others sort after
function langOrder(lang: ReviewLanguage): number {
  return lang === "zh" ? 0 : 1;
}

function getSlotCounts(overallRating: number): { positive: number; critical: number } {
  if (overallRating >= 4.5) return { positive: 3, critical: 1 };
  if (overallRating >= 3.5) return { positive: 2, critical: 2 };
  return { positive: 1, critical: 3 };
}

function attachLabels(
  review: { text: string; rating: number; author: string; publishTime?: string | null; language: ReviewLanguage },
  dishes: string[],
): ReviewSnippet {
  const lower = review.text.toLowerCase();
  const labels = new Set<string>();
  for (const dish of dishes) {
    if (dish && review.text.includes(dish)) labels.add(dish);
  }
  for (const rule of REVIEW_LABEL_RULES) {
    if (rule.keywords.some((keyword) => lower.includes(keyword))) {
      labels.add(rule.label);
    }
  }
  return { ...review, labels: [...labels].slice(0, 4) };
}

export async function getShopReviewInsights(shopId: number): Promise<ShopReviewInsights | null> {
  const shop = await getExtractedShop(shopId);
  const manifestReviews = getShopManifestReviews(shopId);
  if (!shop && !manifestReviews.length) return null;

  const dishes = parseList(shop?.ai_extracted?.signature_dishes);
  const overallRating = shop?.rating ?? 4.0;

  const legacyReviews = (shop?.reviews ?? []).map((review) => ({
    author: review.author ?? "匿名評論",
    rating: Number(review.rating ?? 0),
    text: normalizeText(review.text),
    publishTime: review.publish_time ?? null,
  }));

  const manifestMapped = manifestReviews.map((review) => ({
    author: review.author ?? "匿名評論",
    rating: Number(review.rating ?? 0),
    text: normalizeText(review.text),
    publishTime: review.publishTime ?? null,
  }));

  const seenReviews = new Set<string>();
  const reviews = [...manifestMapped, ...legacyReviews]
    .map((review) => ({ ...review, language: detectLanguage(review.text) }))
    .filter((review) => {
      const key = `${review.author}:${review.text}`;
      if (!review.text || seenReviews.has(key)) return false;
      seenReviews.add(key);
      return true;
    });

  const nonEmpty = reviews.filter((r) => r.text);

  // Sort pool: zh first, then by recency desc, then informativeness desc
  const sortPool = (pool: typeof nonEmpty) =>
    [...pool].sort(
      (a, b) =>
        langOrder(a.language) - langOrder(b.language) ||
        recencyScore(b.publishTime) - recencyScore(a.publishTime) ||
        informativenessScore(b.text) - informativenessScore(a.text),
    );

  const used = new Set<string>();
  const key = (r: { author: string; text: string }) => r.author + r.text;

  const pickN = (candidates: typeof nonEmpty, n: number): typeof nonEmpty => {
    const sorted = sortPool(candidates);
    const result: typeof nonEmpty = [];
    for (const r of sorted) {
      if (result.length >= n) break;
      if (!used.has(key(r))) {
        result.push(r);
        used.add(key(r));
      }
    }
    return result;
  };

  const { positive: posCount, critical: critCount } = getSlotCounts(overallRating);

  const positivePool = nonEmpty.filter((r) => r.rating >= 4);
  const criticalPool = nonEmpty.filter((r) => r.rating > 0 && r.rating <= 3);

  const positiveSlots = pickN(positivePool, posCount);
  const criticalSlots = pickN(criticalPool, critCount);

  // Fill remaining slots with most informative (any rating), zh first
  const remaining = 5 - positiveSlots.length - criticalSlots.length;
  const infoFill = remaining > 0
    ? pickN(
        [...nonEmpty].sort(
          (a, b) =>
            langOrder(a.language) - langOrder(b.language) ||
            informativenessScore(b.text) - informativenessScore(a.text) ||
            recencyScore(b.publishTime) - recencyScore(a.publishTime),
        ),
        remaining,
      )
    : [];

  const raw = [...positiveSlots, ...criticalSlots, ...infoFill];

  // Fallback: if still fewer than 5, fill from nonEmpty
  if (raw.length < 5) {
    const fallback = sortPool(nonEmpty).filter((r) => !used.has(key(r)));
    for (const r of fallback) {
      if (raw.length >= 5) break;
      raw.push(r);
      used.add(key(r));
    }
  }

  // Final sort: zh first, then recency desc, then informativeness desc
  const selectedReviews = raw
    .sort(
      (a, b) =>
        langOrder(a.language) - langOrder(b.language) ||
        recencyScore(b.publishTime) - recencyScore(a.publishTime) ||
        informativenessScore(b.text) - informativenessScore(a.text),
    )
    .map((review) => attachLabels(review, dishes));

  const negativeReviews = nonEmpty.filter((r) => r.rating > 0 && r.rating <= 3);

  const advice = ADVICE_RULES
    .map((rule) => ({
      label: rule.label,
      detail: rule.detail,
      matches: negativeReviews.filter((r) => rule.keywords.some((kw) => r.text.toLowerCase().includes(kw))).length,
    }))
    .filter((rule) => rule.matches >= 2)
    .sort((a, b) => b.matches - a.matches)
    .slice(0, 4)
    .map((rule) => ({ label: rule.label, detail: rule.detail }));

  return {
    selectedReviews,
    advice,
    totalReviews: reviews.length,
    nonEmptyReviews: nonEmpty.length,
  };
}
