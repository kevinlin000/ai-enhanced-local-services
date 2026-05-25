/**
 * Server-side proxy for TapPay JS SDK.
 * 原因：TapPay CDN 擋 localhost Referer（403），server-side fetch 無 browser Referer，
 * CDN 放行後回傳 JS，前端改從 /api/tappay-sdk 載入即可。
 * Production 改回直接載 CDN，刪此 route。
 */
export async function GET() {
  const sdkUrl = "https://js.tappaysdk.com/sdk/tpdirect/v5.17.1";

  try {
    const res = await fetch(sdkUrl, {
      headers: {
        "User-Agent": "Mozilla/5.0 (compatible; Next.js server proxy)",
      },
      next: { revalidate: 3600 }, // 快取 1 小時
    });

    if (!res.ok) {
      return new Response(`// TapPay SDK proxy failed: ${res.status} ${res.statusText}`, {
        status: 502,
        headers: { "Content-Type": "application/javascript" },
      });
    }

    const js = await res.text();
    return new Response(js, {
      headers: {
        "Content-Type": "application/javascript; charset=utf-8",
        "Cache-Control": "public, max-age=3600",
      },
    });
  } catch (e: any) {
    return new Response(`// TapPay SDK proxy error: ${e?.message}`, {
      status: 502,
      headers: { "Content-Type": "application/javascript" },
    });
  }
}
