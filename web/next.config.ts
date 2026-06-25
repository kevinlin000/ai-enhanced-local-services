import type { NextConfig } from "next";

const javaApiProxyTarget = process.env.JAVA_API_PROXY_TARGET ?? "http://localhost:8081";
const aiApiProxyTarget = process.env.AI_API_PROXY_TARGET ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  // 允許 ngrok tunnel 做為 dev origin（HMR WebSocket + hydration）
  allowedDevOrigins: ["*.ngrok-free.app", "*.ngrok-free.dev", "*.ngrok.io"],

  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), payment=()" },
          {
            key: "Content-Security-Policy-Report-Only",
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-inline' 'unsafe-eval' https:",
              "style-src 'self' 'unsafe-inline' https:",
              "img-src 'self' data: blob: https:",
              "font-src 'self' data: https:",
              "connect-src 'self' http://localhost:* http://127.0.0.1:* https: ws: wss:",
              "frame-src https:",
              "object-src 'none'",
              "base-uri 'self'",
              "frame-ancestors 'none'",
            ].join("; "),
          },
        ],
      },
    ];
  },

  // Server-side proxy：/api/java/* → Java API.
  // 解決 HTTPS dev 環境下 mixed content（HTTPS 頁面不能打 HTTP API）
  // 部署時用 JAVA_API_PROXY_TARGET / AI_API_PROXY_TARGET 指到公開 backend。
  async rewrites() {
    return [
      {
        // /api/java/api/shop/count → {JAVA_API_PROXY_TARGET}/api/shop/count
        source: "/api/java/:path*",
        destination: `${javaApiProxyTarget}/:path*`,
      },
      {
        // /api/python/api/ai/search → {AI_API_PROXY_TARGET}/api/ai/search
        source: "/api/python/:path*",
        destination: `${aiApiProxyTarget}/:path*`,
      },
      {
        // /api/ai/search → {AI_API_PROXY_TARGET}/api/ai/search
        // Cleaner proxy: AI calls use /api/ai/* directly (no double-prefix)
        source: "/api/ai/:path*",
        destination: `${aiApiProxyTarget}/api/ai/:path*`,
      },
      {
        // LINE webhook endpoints exposed through the public ngrok web domain.
        source: "/api/line/:path*",
        destination: `${aiApiProxyTarget}/api/line/:path*`,
      },
      {
        // LINE rich-menu / Flex card actions such as /line/book/* live in AI service.
        source: "/line/:path*",
        destination: `${aiApiProxyTarget}/line/:path*`,
      },
    ];
  },
};

export default nextConfig;
