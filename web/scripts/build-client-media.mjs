// 從 data/shop-media.json 產出瘦身版 client manifest。
// 完整檔 7MB+（評論全文佔 3MB+）只留在 server；client bundle 只需要
// 照片 URL、overview 與評論「數量」，瘦身後約 0.3MB。
import { readFileSync, writeFileSync, mkdirSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const src = resolve(__dirname, "../data/shop-media.json");
const dest = resolve(__dirname, "../lib/_generated/shop-media.client.json");

const payload = JSON.parse(readFileSync(src, "utf8"));
const shops = {};
for (const [id, shop] of Object.entries(payload.shops ?? {})) {
  shops[id] = {
    photoUrls: shop.photoUrls ?? [],
    coverUrl: shop.coverUrl ?? null,
    galleryUrls: shop.galleryUrls ?? [],
    overview: shop.overview ?? null,
    reviewCount: (shop.reviews ?? []).filter((review) => review.text).length,
  };
}

mkdirSync(dirname(dest), { recursive: true });
writeFileSync(dest, JSON.stringify({ shops }));
console.log(
  `client media synced: ${Object.keys(shops).length} shops → web/lib/_generated/shop-media.client.json`,
);
