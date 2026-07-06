import assert from "node:assert/strict";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

test("missing ETL raw directory falls back to an empty map", async () => {
  const originalCwd = process.cwd();
  const isolatedCwd = mkdtempSync(join(tmpdir(), "bytebites-web-"));

  try {
    process.chdir(isolatedCwd);
    const { loadExtractedShopMap } = await import(`../lib/extractedShops.ts?missing=${Date.now()}`);
    const shops = await loadExtractedShopMap();
    assert.equal(shops.size, 0);
  } finally {
    process.chdir(originalCwd);
    rmSync(isolatedCwd, { recursive: true, force: true });
  }
});
