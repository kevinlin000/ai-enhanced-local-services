import { readdir, readFile } from "node:fs/promises";
import path from "node:path";

type RawReview = {
  author?: string | null;
  rating?: number | null;
  text?: string | null;
  publish_time?: string | null;
  source?: string | null;
};

type ExtractedShop = {
  shop_id?: number;
  display_name?: string;
  reviews?: RawReview[];
  ai_extracted?: {
    signature_dishes?: string[] | string;
  };
};

type ExtractedPayload = {
  shops?: ExtractedShop[];
};

export type ReviewSnippet = {
  author: string;
  rating: number;
  text: string;
  publishTime?: string | null;
  labels: string[];
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

const RAW_DIR = path.join(
  process.cwd(),
  "..",
  "etl-pipeline",
  "data",
  "raw",
);

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
  const chineseChars = (cleaned.match(/[\u4e00-\u9fff]/g) ?? []).length;
  return chineseChars >= Math.max(8, Math.floor(cleaned.length * 0.2));
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

function reviewValueScore(review: RawReview) {
  const text = normalizeText(review.text);
  if (!text) return 0;

  let score = Math.min(text.length, 600) / 30;
  if (hasEnoughChinese(text)) score += 6;
  if ((review.rating ?? 0) >= 4) score += 2;
  if ((review.rating ?? 0) <= 3) score += 1;
  if (/[0-9]+|元|\$|NT\$/.test(text)) score += 3;
  if (/推薦|必點|招牌|口感|湯頭|服務|環境|氣氛|包廂|上菜|訂位|排隊/.test(text)) score += 4;
  return score;
}

async function latestExtractedFile() {
  const files = await readdir(RAW_DIR);
  const candidates = files.filter((name) => /^places_extracted_\d{8}_\d{6}\.json$/.test(name)).sort();
  const latest = candidates.at(-1);
  if (!latest) return null;
  return path.join(RAW_DIR, latest);
}

export async function getShopReviewInsights(shopId: number): Promise<ShopReviewInsights | null> {
  const latest = await latestExtractedFile();
  if (!latest) return null;

  const payload = JSON.parse(await readFile(latest, "utf-8")) as ExtractedPayload;
  const shop = payload.shops?.find((item) => item.shop_id === shopId);
  if (!shop) return null;

  const dishes = parseList(shop.ai_extracted?.signature_dishes);

  const reviews = (shop.reviews ?? []).map((review) => ({
    author: review.author ?? "匿名評論",
    rating: Number(review.rating ?? 0),
    text: normalizeText(review.text),
    publishTime: review.publish_time ?? null,
  }));

  const nonEmpty = reviews.filter((review) => review.text);
  const chineseFirst = nonEmpty.filter((review) => hasEnoughChinese(review.text));
  const reviewPool = (chineseFirst.length >= 3 ? chineseFirst : nonEmpty);

  const selectedReviews = [...reviewPool]
    .sort((a, b) => reviewValueScore(b) - reviewValueScore(a))
    .slice(0, 5)
    .map((review) => {
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
      return {
        ...review,
        labels: [...labels].slice(0, 4),
      };
    });

  const advice = ADVICE_RULES
    .map((rule) => ({
      label: rule.label,
      detail: rule.detail,
      matches: nonEmpty.filter((review) => rule.keywords.some((keyword) => review.text.toLowerCase().includes(keyword))).length,
    }))
    .filter((rule) => rule.matches > 0)
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
