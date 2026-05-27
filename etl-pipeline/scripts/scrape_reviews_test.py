"""
單店評論爬蟲原型 — 用 Playwright + Chromium
目標：Google Maps place_id → 最多 20 則評論
用法：uv run python scripts/scrape_reviews_test.py
"""
import asyncio
import json
import time
from playwright.async_api import async_playwright

PLACE_ID = "ChIJ41wbgbqrQjQR75mxQgbywys"  # 一蘭拉麵台灣台北本店
SHOP_NAME = "一蘭拉麵台灣台北本店"
TARGET_REVIEWS = 20
HEADLESS = True


async def scrape_reviews(place_id: str, target: int = 20) -> list[dict]:
    url = f"https://www.google.com/maps/place/?q=place_id:{place_id}&hl=zh-TW"
    reviews: list[dict] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        ctx = await browser.new_context(
            locale="zh-TW",
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = await ctx.new_page()

        print(f"[1] 開啟 {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        # ── 點「評論」tab ──────────────────────────────────────────────────
        review_tab = page.locator('[data-tab-index="1"], [aria-label*="評論"], button:has-text("評論")').first
        try:
            await review_tab.click(timeout=5000)
            print("[2] 點評論 tab")
        except Exception:
            # 有些頁面直接顯示評論列表，不需點 tab
            print("[2] 無評論 tab，繼續")
        await page.wait_for_timeout(2000)

        # ── 捲動載入評論 ───────────────────────────────────────────────────
        scroll_container = page.locator('[class*="review"], div[aria-label*="評論"]').first
        print("[3] 開始捲動載入評論...")
        for i in range(8):
            count_before = await page.locator('[data-review-id]').count()
            await page.evaluate("""
                const els = document.querySelectorAll('[role="feed"], .review-list, div[aria-label]');
                for (const el of els) { el.scrollTo(0, el.scrollHeight); }
                window.scrollTo(0, document.body.scrollHeight);
            """)
            await page.wait_for_timeout(1500)
            count_after = await page.locator('[data-review-id]').count()
            print(f"  scroll {i+1}: {count_before} → {count_after} 則")
            if count_after >= target:
                break

        # ── 展開全文 ───────────────────────────────────────────────────────
        more_buttons = await page.locator('[aria-label*="更多"], button:has-text("更多"), [jsaction*="pane.review.expandReview"]').all()
        for btn in more_buttons[:target]:
            try:
                await btn.click(timeout=1000)
            except Exception:
                pass
        await page.wait_for_timeout(500)

        # ── 抓評論節點 ────────────────────────────────────────────────────
        review_nodes = await page.locator('[data-review-id]').all()
        print(f"[4] 找到 {len(review_nodes)} 個 data-review-id 節點")

        for node in review_nodes[:target]:
            try:
                # 評分
                stars_el = node.locator('[aria-label*="顆星"], [aria-label*="star"]').first
                stars_text = await stars_el.get_attribute("aria-label", timeout=1000) or ""
                rating = None
                for ch in stars_text:
                    if ch.isdigit():
                        rating = int(ch)
                        break

                # 評論文字
                text_el = node.locator('[class*="review-full-text"], [class*="MyEned"], [jsaction*="expandReview"] + *, span.wiI7pd').first
                text = (await text_el.inner_text(timeout=1000)).strip() if await text_el.count() else ""
                if not text:
                    text_el2 = node.locator("span").nth(3)
                    text = (await text_el2.inner_text(timeout=500)).strip() if await text_el2.count() else ""

                # 作者
                author_el = node.locator('[class*="author"], .d4r55, [aria-label*="作者"]').first
                author = (await author_el.inner_text(timeout=1000)).strip() if await author_el.count() else ""

                # 時間
                time_el = node.locator('[class*="date"], .rsqaWe, [aria-label*="前"]').first
                rel_time = (await time_el.inner_text(timeout=1000)).strip() if await time_el.count() else ""

                reviews.append({
                    "author": author or None,
                    "rating": rating,
                    "text": text or None,
                    "relative_time": rel_time or None,
                    "source": "google_maps_scrape",
                })
            except Exception as exc:
                print(f"  節點解析失敗: {exc}")
                continue

        await browser.close()

    return reviews


async def main():
    t0 = time.time()
    print(f"\n=== 目標：{SHOP_NAME} ({PLACE_ID}) ===\n")
    reviews = await scrape_reviews(PLACE_ID, TARGET_REVIEWS)
    elapsed = time.time() - t0

    print(f"\n[結果] 抓到 {len(reviews)} 則評論，耗時 {elapsed:.1f}s")
    print("\n--- 前 3 則 ---")
    for i, r in enumerate(reviews[:3], 1):
        print(f"\n[{i}] ★{r['rating']} | {r['author']} | {r['relative_time']}")
        print(f"    {(r['text'] or '')[:120]}")

    out = {
        "place_id": PLACE_ID,
        "shop_name": SHOP_NAME,
        "elapsed_sec": round(elapsed, 1),
        "review_count": len(reviews),
        "reviews": reviews,
    }
    outpath = "data/raw/test_reviews_scrape.json"
    import pathlib
    pathlib.Path("data/raw").mkdir(parents=True, exist_ok=True)
    pathlib.Path(outpath).write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"\n[OUTPUT] {outpath}")
    print(f"\n欄位確認: {list(reviews[0].keys()) if reviews else '無資料'}")


asyncio.run(main())
