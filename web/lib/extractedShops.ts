import { readdir, readFile } from "node:fs/promises";
import path from "node:path";

export type ExtractedShopRecord = {
  shop_id?: number;
  display_name?: string;
  district?: string;
  rating?: number | null;
  user_rating_count?: number | null;
  reviews?: {
    author?: string | null;
    rating?: number | null;
    text?: string | null;
    publish_time?: string | null;
    source?: string | null;
  }[];
  ai_extracted?: {
    price_per_person?: string;
    booking_difficulty?: string;
    atmosphere_tags?: string[] | string;
    signature_dishes?: string[] | string;
  };
};

type ExtractedPayload = {
  shops?: ExtractedShopRecord[];
};

const RAW_DIR = path.join(process.cwd(), "..", "etl-pipeline", "data", "raw");

let cache: Map<number, ExtractedShopRecord> | null = null;
let cacheSignature: string | null = null;

export async function loadExtractedShopMap() {
  const files = await readdir(RAW_DIR);
  const candidates = files
    .filter((name) => /^places_extracted_\d{8}_\d{6}\.json$/.test(name))
    .sort();
  const signature = candidates.join("|");

  if (cache && cacheSignature === signature) return cache;

  const merged = new Map<number, ExtractedShopRecord>();

  for (const file of candidates) {
    const fullPath = path.join(RAW_DIR, file);
    const payload = JSON.parse(await readFile(fullPath, "utf-8")) as ExtractedPayload;
    for (const shop of payload.shops ?? []) {
      const shopId = shop.shop_id;
      if (!shopId) continue;
      // Deduplicate reviews: same author + normalized whitespace text = same review
      if (shop.reviews) {
        const seen = new Set<string>();
        shop.reviews = shop.reviews.filter((r) => {
          const key = `${r.author ?? ""}||${(r.text ?? "").replace(/\s+/g, " ").trim()}`;
          if (seen.has(key)) return false;
          seen.add(key);
          return true;
        });
      }
      merged.set(shopId, shop);
    }
  }

  cache = merged;
  cacheSignature = signature;
  return merged;
}

export async function getExtractedShop(shopId: number) {
  const shopMap = await loadExtractedShopMap();
  return shopMap.get(shopId) ?? null;
}
