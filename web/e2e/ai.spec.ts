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

async function mockPendingPaymentTransaction(page: Page) {
  await page.route("**/api/ai/agent/stream", async (route) => {
    const holdExpiresAt = new Date(Date.now() + 10 * 60 * 1000).toISOString();
    const transaction = {
      kind: "booking",
      success: true,
      status: "PENDING_PAYMENT",
      shop_id: 9101,
      shop_name: "測試火鍋店",
      booking_code: "BK-E2E-PAY-001",
      people: 2,
      date: "2026-06-10",
      time: "19:00",
      table_type: "一般座位",
      needs_deposit: true,
      deposit_total: 600,
      hold_expires_at: holdExpiresAt,
      hold_minutes: 10,
    };
    const events = [
      { type: "agent_start", session_id: "e2e-payment-session" },
      { type: "message_update", content: "已建立訂位，等待訂金付款。" },
      {
        type: "agent_end",
        answer: "已建立訂位，付款後才會完成保留。",
        transaction,
        tool_result: { transaction },
        tools_used: ["create_booking"],
        session_id: "e2e-payment-session",
      },
    ];
    await route.fulfill({
      contentType: "text/event-stream; charset=utf-8",
      body: events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join(""),
    });
  });
  await page.route("**/api/java/api/booking/pay-test", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        data: {
          bookingCode: "BK-E2E-PAY-001",
          rec_trade_id: "E2E-TRADE-PAID",
          amount: 600,
          status: "PAID",
          note: "Demo paid",
        },
      }),
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

test("AI page updates pending payment transaction after demo payment succeeds", async ({ page }) => {
  await mockAuthenticatedUser(page);
  await mockPendingPaymentTransaction(page);

  await page.goto("/ai");

  const input = page.getByPlaceholder("找餐廳 問 ByteBites AI");
  await expect(input).toBeEnabled();
  await input.fill("幫我訂測試火鍋店明天晚上 7 點 2 人");
  await page.getByRole("button", { name: "送出" }).click();

  await expect(page.getByText("訂位待付款")).toBeVisible();
  await expect(page.getByText("BK-E2E-PAY-001")).toBeVisible();
  await expect(page.getByText("狀態：待付款")).toBeVisible();

  await page.getByRole("button", { name: /確認以信用卡 Demo支付 NT\$ 600/ }).click();

  await expect(page.getByText("訂位確認")).toBeVisible();
  await expect(page.getByText("PAID", { exact: true })).toBeVisible();
  await expect(page.getByText("狀態：已付款")).toBeVisible();
  await expect(page.getByText("交易編號：E2E-TRADE-PAID")).toBeVisible();
  await expect(page.getByText("信用卡 Demo 付款完成：Demo paid")).toBeVisible();
});

test("mobile AI concierge renders the shared agent result contract", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockAuthenticatedUser(page);
  await mockAgentRecommendation(page);

  await page.goto("/");

  await page.getByRole("button", { name: "AI Concierge" }).click();
  const input = page.getByPlaceholder("輸入你想吃什麼...");
  await expect(input).toBeEnabled();
  await input.fill("推薦中山區漢堡");
  await page.getByRole("button", { name: "送出" }).click();

  await expect(page.getByText("中山區符合條件較少，我先擴大到台北漢堡店")).toBeVisible();
  await expect(page.getByText("測試漢堡 B").first()).toBeVisible();
  await expect(page.getByText("測試漢堡 A").first()).toBeVisible();
  await expect(page.getByText("測試漢堡 C").first()).toBeVisible();
  await expect(page.getByText("done duplicate should not overwrite agent_end")).toHaveCount(0);

  await page.getByRole("link", { name: /查看完整卡片與比較表/ }).click();
  await expect(page).toHaveURL(/\/ai\?q=.*%E6%8E%A8%E8%96%A6%E4%B8%AD%E5%B1%B1%E5%8D%80%E6%BC%A2%E5%A0%A1/);
});
