import payload from "@/data/shop-media.json";

export type ShopOverview = {
  price_overview?: string;
  price_report_count?: number;
  price_buckets?: string[] | { label: string; count?: number; share?: number }[];
  popular_time?: { hour?: string; status?: string };
  visit_duration?: string;
};

type PhotoPayload = {
  shops?: Record<
    string,
    {
      photoUrls?: string[];
      coverUrl?: string | null;
      galleryUrls?: string[];
      overview?: ShopOverview;
    }
  >;
};

const PHOTO_DATA = payload as PhotoPayload;
const COVER_OVERRIDES: Record<number, { coverIndex?: number; coverUrl?: string; disableReviewPhotos?: boolean }> = {
  10100: { coverIndex: 0 }, // 一蘭別館：先用現有評論圖，不退回 icon
  10104: { coverIndex: 0 }, // 饗饗：用 overview 正圖
  10112: { coverIndex: 0 }, // HOOTERS：先用 overview 圖，文字污染另行重抓
  10115: { coverIndex: 1 }, // 辛殿：避開 122x92 overview 縮圖，改用較清楚食物照
  10127: { coverIndex: 1 }, // 下港吔：食物比超寬場景穩
  10131: { coverIndex: 3 }, // 詹記：避開過近特寫
  10149: { coverIndex: 2 }, // 夏慕尼南昌：偏料理成品
  10108: { coverIndex: 2 }, // 布納：避開帳單
  10111: { coverIndex: 2 }, // 鼎泰豐A4：避開只拍人手/空盤
  10147: { coverIndex: 3 }, // 泰和樓：避開菜單/店外
  10152: { coverIndex: 0 }, // 和牛涮：目前僅單張，保留
  10158: { coverIndex: 4 }, // 大樹先生的家：避開小孩
  10169: { coverIndex: 3 }, // 蔬食百匯：避開單盤近拍
  10171: { coverIndex: 4 }, // 肉執事：避開菜單頁/桌角
};

function photoScore(url: string) {
  let score = 0;
  const size = url.match(/=w(\d+)-h(\d+)-/);
  if (size) {
    const width = Number(size[1]);
    const height = Number(size[2]);
    if (width > height) score += 6;
    if (width / Math.max(height, 1) >= 1.3) score += 4;
    if (width >= 600) score += 2;
  }
  return score;
}

export function getShopPhotoUrlsFromManifest(shopId: number): string[] {
  const override = COVER_OVERRIDES[shopId];
  if (override?.disableReviewPhotos) return [];
  const shop = PHOTO_DATA.shops?.[String(shopId)];
  return (shop?.galleryUrls ?? shop?.photoUrls ?? []).filter(Boolean);
}

export function getShopOverview(shopId: number): ShopOverview | null {
  return PHOTO_DATA.shops?.[String(shopId)]?.overview ?? null;
}

export function getShopCoverPhoto(shopId: number): string | null {
  const override = COVER_OVERRIDES[shopId];
  if (override?.coverUrl) return override.coverUrl;
  if (override?.disableReviewPhotos) return null;
  const shop = PHOTO_DATA.shops?.[String(shopId)];
  const urls = getShopPhotoUrlsFromManifest(shopId);
  if (override?.coverIndex != null && urls[override.coverIndex]) {
    return urls[override.coverIndex]!;
  }
  if (shop?.coverUrl) return shop.coverUrl;
  if (!urls.length) return null;
  return [...urls].sort((a, b) => photoScore(b) - photoScore(a))[0] ?? null;
}

export function getShopGalleryPhotos(shopId: number): string[] {
  const urls = getShopPhotoUrlsFromManifest(shopId);
  const cover = getShopCoverPhoto(shopId);
  if (!cover) return urls;
  return [cover, ...urls.filter((url) => url !== cover)];
}

export function getBestShopCardPhoto(
  shopId: number,
  fallbackImage?: string | null,
) {
  return getShopCoverPhoto(shopId) ?? fallbackImage ?? null;
}
