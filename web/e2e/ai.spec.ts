import { expect, test, type Page } from "@playwright/test";

async function mockAuthenticatedUser(page: Page) {
  await page.addInitScript(() => {
    localStorage.setItem("bytebites_token", "e2e-token");
  });
  await page.route("**/api/java/api/auth/me", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        data: {
          id: 9001,
          displayName: "E2E 使用者",
          lineLinked: true,
          lineUserId: "U-e2e",
        },
      }),
    });
  });
}

async function mockAgentRecommendation(page: Page) {
  await page.route("**/api/shop/*/reviews", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        selectedReviews: [
          { rating: 5, text: "漢堡肉汁足，薯條也好吃。", labels: ["菜色", "環境"] },
        ],
        totalReviews: 12,
        nonEmptyReviews: 12,
      }),
    });
  });
  await page.route("**/api/java/api/shop/*/absa", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ success: true, data: { aspects: "[]" } }),
    });
  });
  await page.route("**/api/ai/agent/stream", async (route) => {
    const events = [
      { type: "agent_start", session_id: "e2e-session" },
      { type: "turn_start", query: "推薦中山區漢堡", session_id: "e2e-session" },
      { type: "tool_execution_start", name: "semantic_shop_search", session_id: "e2e-session" },
      { type: "tool_execution_end", name: "semantic_shop_search", session_id: "e2e-session" },
      { type: "message_update", content: "我幫你整理 3 間漢堡店。" },
      {
        type: "agent_end",
        answer: "我幫你整理 3 間漢堡店。",
        tools_used: ["semantic_shop_search"],
        recommended_shop_ids: [9002, 9001, 9003],
        scope_note: "中山區符合條件較少，我先擴大到台北漢堡店，整理 3 間符合需求的餐廳。",
        tool_result: {
          shops: [
            {
              shop_id: 9001,
              name: "測試漢堡 A",
              district: "中山",
              mrt_station: "中山",
              avg_price: 420,
              price_per_person: "NT$ 350-500",
              ai_summary: "中山站附近的美式漢堡店，適合朋友聚餐。",
              signature_dishes: ["牛肉漢堡", "薯條"],
              atmosphere_tags: ["朋友聚餐", "美式"],
              booking_difficulty: "可線上訂位",
            },
            {
              shop_id: 9002,
              name: "測試漢堡 B",
              district: "大安",
              mrt_station: "忠孝復興",
              avg_price: 520,
              price_per_person: "NT$ 450-650",
              ai_summary: "肉感厚實，適合想吃高級漢堡的晚餐。",
              signature_dishes: ["厚切牛肉堡", "奶昔"],
              atmosphere_tags: ["約會", "餐酒館"],
              booking_difficulty: "可線上訂位，建議提前",
            },
            {
              shop_id: 9003,
              name: "測試漢堡 C",
              district: "信義",
              mrt_station: "市政府",
              avg_price: 390,
              price_per_person: "NT$ 300-450",
              ai_summary: "交通方便，適合快速聚餐。",
              signature_dishes: ["起司漢堡", "洋蔥圈"],
              atmosphere_tags: ["快速用餐", "朋友聚餐"],
              booking_difficulty: "可線上訂位",
            },
          ],
        },
        session_id: "e2e-session",
      },
      {
        type: "done",
        answer: "done duplicate should not overwrite agent_end",
        tools_used: ["semantic_shop_search"],
        tool_result: { shops: [] },
        session_id: "e2e-session",
      },
    ];
    await route.fulfill({
      contentType: "text/event-stream; charset=utf-8",
      body: events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join(""),
    });
  });
}

test("AI page blocks chat when user is not logged in", async ({ page }) => {
  await page.goto("/ai");

  await expect(page.getByRole("button", { name: "用 LINE 登入後開始" })).toBeVisible();
  await expect(page.getByPlaceholder("找餐廳 問 ByteBites AI")).toBeDisabled();
  await expect(page.getByRole("button", { name: "送出" })).toBeDisabled();
});

test("AI page renders mocked recommendation cards and comparison table", async ({ page }) => {
  await mockAuthenticatedUser(page);
  await mockAgentRecommendation(page);

  await page.goto("/ai");

  const input = page.getByPlaceholder("找餐廳 問 ByteBites AI");
  await expect(input).toBeEnabled();
  await input.fill("推薦中山區漢堡");
  await page.getByRole("button", { name: "送出" }).click();

  await expect(page.getByText("中山區符合條件較少，我先擴大到台北漢堡店")).toBeVisible();
  await expect(page.getByText("測試漢堡 B").first()).toBeVisible();
  await expect(page.getByText("測試漢堡 A").first()).toBeVisible();
  await expect(page.getByText("測試漢堡 C").first()).toBeVisible();
  await expect(page.getByText("查看詳情 / 訂位")).toHaveCount(3);
  await expect(page.getByRole("heading", { name: "快速比較" })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "特色亮點" })).toBeVisible();
  await expect(page.getByText("done duplicate should not overwrite agent_end")).toHaveCount(0);
});
