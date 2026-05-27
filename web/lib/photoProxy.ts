export function proxyImageUrl(url?: string | null) {
  if (!url) return null;
  return `/api/photo?src=${encodeURIComponent(url)}`;
}
