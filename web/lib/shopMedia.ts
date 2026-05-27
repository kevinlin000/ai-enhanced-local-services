import { getShopPhotoUrlsFromManifest } from "@/lib/shopPhotoManifest";

export async function getShopPhotoUrls(shopId: number): Promise<string[]> {
  return getShopPhotoUrlsFromManifest(shopId);
}
