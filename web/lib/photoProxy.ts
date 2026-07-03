export function proxyImageUrl(url?: string | null) {
  if (!url) return null;
  if (url.startsWith("/") && !url.startsWith("//")) return url;
  return `/api/photo?src=${encodeURIComponent(url)}`;
}
