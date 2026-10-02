import { chromium } from "@playwright/test";

const BASE = "https://bytebites-kevin.duckdns.org";
const OUT = "/tmp/bytebites-shots";

const pages = [
  { path: "/merchant", name: "09-merchant-overview" },
  { path: "/merchant#incident-queue", name: "10-merchant-incidents" },
  { path: "/merchant#deposit-queue", name: "11-merchant-deposits" },
  { path: "/merchant#slots", name: "12-merchant-slots" },
];

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await context.newPage();

for (const p of pages) {
  await page.goto(`${BASE}${p.path}`, { waitUntil: "load", timeout: 30000 });
  await page.waitForFunction(() => !document.body.innerText.includes("讀取店家中"), { timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(1800);
  await page.screenshot({ path: `${OUT}/${p.name}.png` });
  console.log(`ok: ${p.name}`);
}

await browser.close();
