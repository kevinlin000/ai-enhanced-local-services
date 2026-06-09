import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";

const root = join(import.meta.dirname, "..");

test("shop detail basic info keeps parking below business hours", () => {
  const source = readFileSync(join(root, "components/ShopDetailTabs.tsx"), "utf8");
  const basicInfo = source.slice(source.indexOf("基本資訊"));

  assert.ok(basicInfo.indexOf("props.address") < basicInfo.indexOf("props.businessHours"));
  assert.ok(basicInfo.indexOf("props.businessHours") < basicInfo.indexOf("props.nearbyParking"));
  assert.ok(basicInfo.indexOf("props.nearbyParking") < basicInfo.indexOf("props.phone"));
  assert.ok(basicInfo.indexOf("props.phone") < basicInfo.indexOf("https://maps.google.com/maps"));
});

test("shop detail parking stays in the basic info section as a compact list", () => {
  const source = readFileSync(join(root, "components/ShopDetailTabs.tsx"), "utf8");

  assert.match(source, /<div id="parking" className="px-4 py-4">/);
  assert.match(source, /mt-3 divide-y rounded-lg border/);
  assert.match(source, /依距離排序，車位以台北市公開即時資料為準/);
  assert.doesNotMatch(source, /導航到停車場/);
});
