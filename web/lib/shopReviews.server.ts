// Server-only：完整 shop-media.json（含評論全文，7MB+）只能從這裡讀。
// Client 端請改用 shopPhotoManifest（瘦身版，只含照片與評論數）。
import payload from "@/data/shop-media.json";

export type ManifestReview = {
  author?: string;
  rating?: number;
  text?: string;
  publishTime?: string | null;
  source?: string;
};

type ReviewPayload = {
  shops?: Record<string, { reviews?: ManifestReview[] }>;
};

const REVIEW_DATA = payload as ReviewPayload;

export function getShopManifestReviews(shopId: number): ManifestReview[] {
  return REVIEW_DATA.shops?.[String(shopId)]?.reviews?.filter((review) => review.text) ?? [];
}
