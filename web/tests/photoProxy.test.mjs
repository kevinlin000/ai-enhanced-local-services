import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";

const root = join(import.meta.dirname, "..");

test("photo proxy degrades to a cacheable placeholder instead of 502", () => {
  const source = readFileSync(join(root, "app/api/photo/route.ts"), "utf8");

  assert.match(source, /function fallbackImage/);
  assert.match(source, /image\/svg\+xml/);
  assert.match(source, /Cache-Control/);
  assert.doesNotMatch(source, /status:\s*502/);
});

test("consumer shell has a restrained product footer while merchant stays separate", () => {
  const source = readFileSync(join(root, "components/AppShell.tsx"), "utf8");
  const merchantBranch = source.slice(source.indexOf('if (pathname.startsWith("/merchant"))'), source.indexOf("return (", source.indexOf('if (pathname.startsWith("/merchant"))') + 1));

  assert.match(source, /function ProductFooter/);
  assert.match(source, /599 家台北 active shops/);
  assert.match(source, /Java transaction state/);
  assert.doesNotMatch(merchantBranch, /ProductFooter/);
});
