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

async function mockNotificationPolls(page: Page) {
  await page.route("**/api/java/api/availability/notifications", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ success: true, data: { unreadCount: 0, items: [] } }),
    });
  });
}

test("my bookings page updates a paid booking after cancellation", async ({ page }) => {
  await mockAuthenticatedUser(page);
  await mockNotificationPolls(page);

  let status: "PAID" | "CANCELED" = "PAID";
  const bookingCode = "BK-E2E-CANCEL-001";
  const booking = () => ({
    bookingCode,
    userId: 9001,
    shopId: 9201,
    shopName: "測試訂位餐廳",
    people: 2,
    date: "2026-06-10",
    time: "19:00",
    tableType: "normal",
    needsDeposit: true,
    depositTotal: 600,
    status,
    paymentTransId: status === "PAID" ? "E2E-PAID-001" : null,
    holdExpiresAt: null,
    holdMinutes: null,
    createdAt: "2026-06-09T10:00:00",
    updatedAt: "2026-06-09T10:00:00",
  });

  await page.route("**/api/java/api/booking/my", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ success: true, data: [booking()] }),
    });
  });
  await page.route(`**/api/java/api/booking/${bookingCode}/cancel`, async (route) => {
    status = "CANCELED";
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ success: true, data: booking() }),
    });
  });

  await page.goto("/my-bookings");

  const card = page.locator("article").filter({ hasText: bookingCode });
  await expect(card).toBeVisible();
  await expect(card.getByText("已付款")).toBeVisible();
  await expect(card.getByText("E2E-PAID-001")).toBeVisible();

  await card.getByRole("button", { name: "取消訂位" }).click();
  await expect(page.getByRole("heading", { name: "確認取消訂位？" })).toBeVisible();
  await expect(page.getByText("取消後此訂位會標記為已取消")).toBeVisible();

  await page.getByRole("button", { name: "確認取消並釋放容量" }).click();

  await expect(page.getByRole("heading", { name: "確認取消訂位？" })).toHaveCount(0);
  await expect(card.getByText("已取消", { exact: true })).toBeVisible();
  await expect(card.getByText("訂位已取消，店家容量已釋放。")).toBeVisible();
  await expect(card.getByRole("button", { name: "取消訂位" })).toHaveCount(0);
});

test("notifications page updates read status and cancels an availability watch", async ({ page }) => {
  await mockAuthenticatedUser(page);

  let notificationStatus: "UNREAD" | "READ" = "UNREAD";
  let watchStatus: "ACTIVE" | "CANCELED" = "ACTIVE";
  const notification = () => ({
    id: 501,
    type: "AVAILABILITY_RELEASED",
    title: "有空位了",
    body: "測試火鍋店 2026-06-10 19:00 釋出 2 人空位，請盡快完成訂位。",
    shopId: 9301,
    shopName: "測試火鍋店",
    watchId: 701,
    status: notificationStatus,
    date: "2026-06-10",
    time: "19:00",
    tableType: "normal",
    people: 2,
    createdAt: "2026-06-09T10:00:00",
    readAt: notificationStatus === "READ" ? "2026-06-09T10:05:00" : null,
  });
  const watch = () => ({
    id: 701,
    shopId: 9301,
    shopName: "測試火鍋店",
    date: "2026-06-10",
    time: "19:00",
    tableType: "normal",
    people: 2,
    status: watchStatus,
    triggeredAt: watchStatus === "ACTIVE" ? null : "2026-06-09T10:01:00",
    expiresAt: "2026-06-10T19:00:00",
    createdAt: "2026-06-09T09:00:00",
  });

  await page.route("**/api/java/api/availability/notifications", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        data: {
          unreadCount: notificationStatus === "UNREAD" ? 1 : 0,
          items: [notification()],
        },
      }),
    });
  });
  await page.route("**/api/java/api/availability/watches", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ success: true, data: [watch()] }),
    });
  });
  await page.route("**/api/java/api/availability/notifications/501/read", async (route) => {
    notificationStatus = "READ";
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ success: true, data: { id: 501, status: "READ" } }),
    });
  });
  await page.route("**/api/java/api/availability/watches/701/cancel", async (route) => {
    watchStatus = "CANCELED";
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ success: true, data: { id: 701, status: "CANCELED" } }),
    });
  });

  await page.goto("/notifications");

  await expect(page.getByText("未讀通知").locator("..").getByText("1")).toBeVisible();
  const notificationCard = page.locator("article").filter({ hasText: "有空位了" });
  await expect(notificationCard.getByText("未讀")).toBeVisible();
  await expect(notificationCard.getByText("測試火鍋店 2026-06-10 19:00")).toBeVisible();

  await notificationCard.getByRole("button", { name: "標記已讀" }).click();

  await expect(page.getByText("未讀通知").locator("..").getByText("0")).toBeVisible();
  await expect(notificationCard.getByText("已讀")).toBeVisible();
  await expect(notificationCard.getByRole("button", { name: "標記已讀" })).toHaveCount(0);

  const watchCard = page.locator("article").filter({ hasText: "追蹤到 2026-06-10T19:00:00" });
  await expect(watchCard.getByText("ACTIVE")).toBeVisible();
  await watchCard.getByRole("button", { name: "取消追蹤" }).click();

  await expect(watchCard.getByText("CANCELED")).toBeVisible();
  await expect(watchCard.getByRole("button", { name: "取消追蹤" })).toHaveCount(0);
});
