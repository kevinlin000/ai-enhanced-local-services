import { chromium } from "@playwright/test";

const BASE = "https://bytebites-kevin.duckdns.org";
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.setViewportSize({ width: 1440, height: 900 });
await page.goto(`${BASE}/merchant`, { waitUntil: "load", timeout: 30000 });
// 等店家選單真的載入資料（不再是「讀取店家中」佔位文字）
await page.waitForFunction(
  () => !document.body.innerText.includes("讀取店家中"),
  { timeout: 15000 },
).catch(() => console.log("warn: still loading after 15s"));
await page.waitForTimeout(1500);
await page.screenshot({ path: "/tmp/bytebites-shots/09-merchant-ops.png" });
console.log("done");
await browser.close();
