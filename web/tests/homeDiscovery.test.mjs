import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";

const root = join(import.meta.dirname, "..");

test("homepage lets visitors search restaurants without choosing a category", () => {
  const source = readFileSync(join(root, "app/page.tsx"), "utf8");

  assert.match(source, /<form action="\/shops" method="get"/);
  assert.match(source, /name="q"/);
  assert.match(source, /placeholder="搜尋餐廳名稱、地址、行政區或捷運站"/);
});

test("homepage category rail uses generated food illustrations with an icon fallback", () => {
  const source = readFileSync(join(root, "app/page.tsx"), "utf8");

  assert.match(source, /CATEGORY_ILLUSTRATIONS/);
  assert.match(source, /\/images\/categories\//);
  assert.match(source, /<Icon className=/);
});
