import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";

const root = join(import.meta.dirname, "..");

test("shop discovery keeps AI mode backed by the full shop cache", () => {
  const source = readFileSync(join(root, "app/shops/page.tsx"), "utf8");

  assert.match(source, /const SEARCH_FETCH_SIZE = 2000;/);
  assert.match(source, /javaApi\.shopSearch\(\{\s*size: SEARCH_FETCH_SIZE\s*\}\)/s);
  assert.doesNotMatch(source, /javaApi\.shopSearch\(\{\s*size: 100\s*\}\)/);
});

test("shop discovery uses icon controls instead of emoji mode labels", () => {
  const source = readFileSync(join(root, "app/shops/page.tsx"), "utf8");

  assert.doesNotMatch(source, /🔍|✨/);
  assert.match(source, /<Search className=/);
  assert.match(source, /<Sparkles className=/);
});
