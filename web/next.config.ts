import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 允許 ngrok tunnel 做為 dev origin（HMR WebSocket + hydration）
  allowedDevOrigins: ["*.ngrok-free.app", "*.ngrok-free.dev", "*.ngrok.io"],

  // Server-side proxy：/api/java/* → http://localhost:8081/api/*
  // 解決 HTTPS dev 環境下 mixed content（HTTPS 頁面不能打 HTTP API）
  // NEXT_PUBLIC_JAVA_API 改成 /api/java 後所有 API call 走這條 rewrite
  async rewrites() {
    return [
      {
        // /api/java/api/shop/count → http://localhost:8081/api/shop/count
        source: "/api/java/:path*",
        destination: "http://localhost:8081/:path*",
      },
      {
        // /api/python/api/ai/search → http://localhost:8000/api/ai/search
        source: "/api/python/:path*",
        destination: "http://localhost:8000/:path*",
      },
    ];
  },
};

export default nextConfig;
