import type { NextConfig } from "next";

const javaApiProxyTarget = process.env.JAVA_API_PROXY_TARGET ?? "http://localhost:8081";
const aiApiProxyTarget = process.env.AI_API_PROXY_TARGET ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  // 允許 ngrok tunnel 做為 dev origin（HMR WebSocket + hydration）
  allowedDevOrigins: ["*.ngrok-free.app", "*.ngrok-free.dev", "*.ngrok.io"],

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
    ];
  },
};

export default nextConfig;
