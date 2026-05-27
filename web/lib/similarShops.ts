import { readdir, readFile } from "node:fs/promises";
import path from "node:path";

type ExtractedShop = {
  shop_id?: number;
  display_name?: string;
  district?: string;
  ai_extracted?: {
    price_per_person?: string;
    booking_difficulty?: string;
    atmosphere_tags?: string[];
    signature_dishes?: string[];
  };
};

type ExtractedPayload = {
  shops?: ExtractedShop[];
};

export type SimilarShop = {
  shopId: number;
  name: string;
  district?: string;
  pricePerPerson?: string;
  bookingDifficulty?: string;
  tags: string[];
  reason: string;
  score: number;
};

const RAW_DIR = path.join(
  process.cwd(),
  "..",
  "etl-pipeline",
  "data",
  "raw",
);

function parseList(value?: string[] | string): string[] {
  if (!value) return [];
  if (Array.isArray(value)) return value.filter(Boolean);
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed.filter(Boolean) : [];
  } catch {
    return [];
  }
}

function priceBand(value?: string) {
  if (!value || value.includes("未提及")) return null;
  const nums = [...value.matchAll(/\d+/g)].map((m) => Number(m[0]));
  if (!nums.length) return null;
  const avg = nums.reduce((a, b) => a + b, 0) / nums.length;
  if (avg < 500) return "low";
  if (avg < 1000) return "mid";
  if (avg < 1600) return "high";
  return "luxury";
}

async function latestExtractedFile() {
  const files = await readdir(RAW_DIR);
  const candidates = files.filter((name) => /^places_extracted_\d{8}_\d{6}\.json$/.test(name)).sort();
  const latest = candidates.at(-1);
  if (!latest) return null;
  return path.join(RAW_DIR, latest);
}

export async function getSimilarShops(shopId: number, limit = 4): Promise<SimilarShop[]> {
  const latest = await latestExtractedFile();
  if (!latest) return [];

  const payload = JSON.parse(await readFile(latest, "utf-8")) as ExtractedPayload;
  const shops = payload.shops ?? [];
  const base = shops.find((shop) => shop.shop_id === shopId);
  if (!base) return [];

  const baseTags = new Set(parseList(base.ai_extracted?.atmosphere_tags));
  const baseDishes = new Set(parseList(base.ai_extracted?.signature_dishes));
  const baseDistrict = base.district;
  const baseBooking = base.ai_extracted?.booking_difficulty ?? "";
  const basePriceBand = priceBand(base.ai_extracted?.price_per_person);

  return shops
    .filter((shop) => shop.shop_id && shop.shop_id !== shopId)
    .map((shop) => {
      const tags = parseList(shop.ai_extracted?.atmosphere_tags);
      const dishes = parseList(shop.ai_extracted?.signature_dishes);
      const overlapTags = tags.filter((tag) => baseTags.has(tag));
      const overlapDishes = dishes.filter((dish) => baseDishes.has(dish));
      const reasons: string[] = [];
      let score = 0;

      if (shop.district && baseDistrict && shop.district === baseDistrict) {
        score += 4;
        reasons.push(`同在${shop.district}`);
      }
      if (overlapTags.length) {
        score += overlapTags.length * 5;
        reasons.push(`同樣適合${overlapTags.slice(0, 2).join("、")}`);
      }
      if (overlapDishes.length) {
        score += overlapDishes.length * 3;
        reasons.push(`評論常提${overlapDishes.slice(0, 2).join("、")}`);
      }
      if (
        shop.ai_extracted?.booking_difficulty &&
        baseBooking &&
        shop.ai_extracted.booking_difficulty === baseBooking
      ) {
        score += 2;
        reasons.push(`同樣是${shop.ai_extracted.booking_difficulty}`);
      }
      if (priceBand(shop.ai_extracted?.price_per_person) && priceBand(shop.ai_extracted?.price_per_person) === basePriceBand) {
        score += 2;
        reasons.push("價位帶相近");
      }

      return {
        shopId: shop.shop_id as number,
        name: shop.display_name ?? `Shop ${shop.shop_id}`,
        district: shop.district,
        pricePerPerson: shop.ai_extracted?.price_per_person,
        bookingDifficulty: shop.ai_extracted?.booking_difficulty,
        tags,
        reason: reasons[0] ?? "評論風格相近",
        score,
      };
    })
    .filter((shop) => shop.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, limit);
}
