import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";

const root = join(import.meta.dirname, "..");

test("restaurant cards use premium dining surfaces across entry points", () => {
  const files = [
    "app/shops/page.tsx",
    "app/favorites/page.tsx",
    "components/AgentShopCard.tsx",
  ];
  const offenders = [];

  for (const file of files) {
    const source = readFileSync(join(root, file), "utf8");
    if (!source.includes("bb-premium-surface")) offenders.push(`${file}: missing bb-premium-surface`);
    if (!source.includes("var(--bb-gold)") && !source.includes("var(--bb-forest)")) {
      offenders.push(`${file}: missing brand accent token`);
    }
  }

  assert.deepEqual(offenders, []);
});

test("restaurant cards avoid emoji-based metadata", () => {
  const files = [
    "app/shops/page.tsx",
    "app/favorites/page.tsx",
    "components/AgentShopCard.tsx",
  ];
  const offenders = [];
  const emojiMetadata = /🍽️|💰|📅|✨|🔥/;

  for (const file of files) {
    const source = readFileSync(join(root, file), "utf8");
    if (emojiMetadata.test(source)) offenders.push(file);
  }

  assert.deepEqual(offenders, []);
});
