import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";

const root = join(import.meta.dirname, "..");
const managementPages = [
  "app/notifications/page.tsx",
  "app/my-bookings/page.tsx",
  "app/favorites/page.tsx",
];

test("management pages use restrained workspace surfaces", () => {
  const offenders = [];
  const heavySurface = /\b(?:rounded-\[[^\]]+\]|rounded-2xl|rounded-3xl|shadow-xl|shadow-2xl|font-black)\b/g;

  for (const file of managementPages) {
    const source = readFileSync(join(root, file), "utf8");
    const matches = source.match(heavySurface);
    if (!matches) continue;
    offenders.push(`${file}: ${[...new Set(matches)].join(", ")}`);
  }

  assert.deepEqual(offenders, []);
});

test("management pages avoid standalone dark marketing heroes", () => {
  const offenders = [];
  const darkHero = /bg-\[#(?:0f3324|123326)\]|Availability Center[\s\S]{0,160}bg-\[#0f3324\]|Saved restaurants[\s\S]{0,160}bg-\[#123326\]/;

  for (const file of managementPages) {
    const source = readFileSync(join(root, file), "utf8");
    if (darkHero.test(source)) offenders.push(file);
  }

  assert.deepEqual(offenders, []);
});
