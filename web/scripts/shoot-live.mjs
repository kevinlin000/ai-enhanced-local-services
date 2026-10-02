import { chromium } from "@playwright/test";
import { mkdirSync } from "fs";

const BASE = "https://bytebites-kevin.duckdns.org";
const OUT = "/tmp/bytebites-shots";
mkdirSync(OUT, { recursive: true });

const pages = [
  { path: "/", name: "01-home", wait: 1500 },
  { path: "/shops", name: "02-shops-list", wait: 1500 },
  { path: "/shops/10556", name: "03-shop-detail", wait: 1800 },
  { path: "/ai", name: "04-ai-chat-empty", wait: 1200 },
  { path: "/my-bookings", name: "05-my-bookings", wait: 1500 },
  { path: "/my-vouchers", name: "06-my-vouchers", wait: 1200 },
  { path: "/favorites", name: "07-favorites", wait: 1200 },
  { path: "/notifications", name: "08-notifications", wait: 1200 },
  { path: "/merchant", name: "09-merchant-ops", wait: 2000 },
  { path: "/showcase", name: "10-showcase", wait: 1500 },
  { path: "/demo", name: "11-demo-guide", wait: 1200 },
];

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await context.newPage();

for (const p of pages) {
  try {
    await page.goto(`${BASE}${p.path}`, { waitUntil: "load", timeout: 30000 });
    await page.waitForTimeout(p.wait);
    await page.screenshot({ path: `${OUT}/${p.name}.png`, fullPage: false });
    console.log(`ok: ${p.name}`);
  } catch (err) {
    console.log(`FAIL: ${p.name} -> ${err.message.split("\n")[0]}`);
  }
}

await browser.close();
