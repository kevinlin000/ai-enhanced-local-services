import type { Metadata } from "next";
import { Geist, Geist_Mono, Noto_Sans_TC } from "next/font/google";
import { AiConcierge } from "@/components/AiConcierge";
import { AppShell } from "@/components/AppShell";
import { NotificationCenterClient } from "@/components/NotificationCenterClient";
import Script from "next/script";
import "./globals.css";

const geist = Geist({
  variable: "--font-geist",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const notoTC = Noto_Sans_TC({
  variable: "--font-noto-tc",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "ByteBites",
  description: "台灣在地點評平台 + AI 應用整合",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="zh-Hant"
      className={`${geist.variable} ${geistMono.variable} ${notoTC.variable} h-full antialiased`}
    >
      <body className="min-h-full">
        <AppShell>
          <NotificationCenterClient />
          {children}
          <AiConcierge />
        </AppShell>
        {/* 開發環境: 透過 server proxy 載入，繞過 localhost Referer 限制 */}
        {/* Production: 換回 https://js.tappaysdk.com/sdk/tpdirect/v5.17.1 並在 portal 加 domain */}
        <Script
          src="/api/tappay-sdk"
          strategy="afterInteractive"
        />
      </body>
    </html>
  );
}
