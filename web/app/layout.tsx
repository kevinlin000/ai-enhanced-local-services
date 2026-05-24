import type { Metadata } from "next";
import { Geist, Geist_Mono, Noto_Sans_TC } from "next/font/google";
import { AiConcierge } from "@/components/AiConcierge";
import { Navbar } from "@/components/Navbar";
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
      <body className="min-h-full flex flex-col">
        <Navbar />
        {children}
        <AiConcierge />
        <Script
          src="https://js.tappaysdk.com/sdk/tpdirect/v5.19.4"
          strategy="beforeInteractive"
        />
      </body>
    </html>
  );
}
