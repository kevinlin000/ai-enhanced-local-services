import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";

const root = join(import.meta.dirname, "..");

test("merchant operations copy frames the page as a command center", () => {
  const source = readFileSync(join(root, "lib/merchantOps.ts"), "utf8");

  assert.match(source, /label:\s*"營運指揮台"/);
  assert.match(source, /先處理會阻塞訂位、付款與通知同步的事項/);
  assert.match(source, /管理離峰補位活動、限量庫存、已搶訂單與可售營收/);
});

test("merchant page connects flash deals to inventory and revenue", () => {
  const source = readFileSync(join(root, "app/merchant/page.tsx"), "utf8");

  assert.match(source, /離峰補位、庫存、已搶營收/);
  assert.match(source, /家庭用餐、訂金付款、開車停車、LINE 同步/);
  assert.match(source, /調低容量即可模擬額滿與空位釋出/);
});

test("merchant feedback is visible in every operations section", () => {
  const source = readFileSync(join(root, "app/merchant/page.tsx"), "utf8");

  const feedback = source.indexOf("{error && (");
  const firstOperationsSection = source.indexOf('id="incident-queue"');
  assert.ok(feedback > 0 && feedback < firstOperationsSection);
});
