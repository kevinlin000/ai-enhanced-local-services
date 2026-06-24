import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";

const root = join(import.meta.dirname, "..");

test("demo guide exposes the operational demo route without date labels", () => {
  const page = readFileSync(join(root, "app/demo/page.tsx"), "utf8");
  const shell = readFileSync(join(root, "components/AppShell.tsx"), "utf8");

  assert.match(shell, /Demo 導覽/);
  assert.match(page, /錄影照這條路線走/);
  assert.match(page, /\/my-bookings/);
  assert.match(page, /\/merchant/);
  assert.match(page, /\/notifications/);
  assert.doesNotMatch(page, /6\/12|6-12|新增/);
});
