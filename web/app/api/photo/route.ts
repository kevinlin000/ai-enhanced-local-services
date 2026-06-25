import { NextRequest } from "next/server";

export const runtime = "nodejs";

function fallbackImage() {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="960" height="640" viewBox="0 0 960 640" role="img" aria-label="ByteBites restaurant photo placeholder">
  <rect width="960" height="640" fill="#f4efe6"/>
  <rect x="96" y="96" width="768" height="448" rx="28" fill="#fffdf8" stroke="#ded8cb" stroke-width="2"/>
  <path d="M360 392h240M390 256h180M420 304h120" stroke="#a78943" stroke-width="18" stroke-linecap="round"/>
  <circle cx="480" cy="320" r="138" fill="none" stroke="#ded8cb" stroke-width="18"/>
  <text x="480" y="484" text-anchor="middle" font-family="Arial, sans-serif" font-size="34" font-weight="600" fill="#706d66">ByteBites</text>
</svg>`;

  return new Response(svg, {
    status: 200,
    headers: {
      "Content-Type": "image/svg+xml; charset=utf-8",
      "Cache-Control": "public, max-age=3600, s-maxage=3600",
    },
  });
}

export async function GET(request: NextRequest) {
  const src = request.nextUrl.searchParams.get("src");
  if (!src) {
    return new Response("missing src", { status: 400 });
  }

  try {
    const upstream = await fetch(src, {
      headers: {
        "User-Agent":
          "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
        Accept: "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        Referer: "https://www.google.com/",
      },
      cache: "force-cache",
    });

    if (!upstream.ok) {
      return fallbackImage();
    }

    const contentType = upstream.headers.get("content-type") ?? "image/jpeg";
    const arrayBuffer = await upstream.arrayBuffer();

    return new Response(arrayBuffer, {
      status: 200,
      headers: {
        "Content-Type": contentType,
        "Cache-Control": "public, max-age=86400, s-maxage=86400",
      },
    });
  } catch {
    return fallbackImage();
  }
}
