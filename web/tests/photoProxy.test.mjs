import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";
import { allowedPhotoSource } from "../lib/photoSource.mjs";

const root = join(import.meta.dirname, "..");

test("photo proxy degrades to a non-cacheable placeholder instead of 502", () => {
  const source = readFileSync(join(root, "app/api/photo/route.ts"), "utf8");

  assert.match(source, /function fallbackImage/);
  assert.match(source, /image\/svg\+xml/);
  assert.match(source, /"Cache-Control": "no-store"/);
  assert.match(source, /"X-Photo-Fallback": "1"/);
  assert.match(source, /signal: AbortSignal\.timeout\(8_000\)/);
  assert.match(source, /startsWith\("image\/"\)/);
  assert.match(source, /redirect: "error"/);
  assert.doesNotMatch(source, /status:\s*502/);
});

test("photo proxy only accepts HTTPS Google image hosts", () => {
  assert.equal(
    allowedPhotoSource("https://lh3.googleusercontent.com/photo.jpg")?.hostname,
    "lh3.googleusercontent.com",
  );

  for (const source of [
    "http://lh3.googleusercontent.com/photo.jpg",
    "https://lh3.googleusercontent.com.evil.example/photo.jpg",
    "http://127.0.0.1:8081/actuator/health",
    "http://169.254.169.254/latest/meta-data/",
    "not-a-url",
  ]) {
    assert.equal(allowedPhotoSource(source), null, source);
  }
});

test("local materialized photos bypass the remote proxy", () => {
  const source = readFileSync(join(root, "lib/photoProxy.ts"), "utf8");

  assert.match(source, /url\.startsWith\("\/"\)/);
  assert.match(source, /!url\.startsWith\("\/\/"\)/);
});

test("local shop covers take priority over legacy remote overrides", () => {
  const source = readFileSync(join(root, "lib/shopPhotoManifest.ts"), "utf8");
  const functionStart = source.indexOf("export function getShopCoverPhoto");
  const localCover = source.indexOf("if (shop?.coverUrl)", functionStart);
  const legacyOverride = source.indexOf("if (override?.coverIndex", functionStart);

  assert.ok(localCover > functionStart);
  assert.ok(localCover < legacyOverride);
});

test("consumer shell has a restrained product footer while merchant stays separate", () => {
  const source = readFileSync(join(root, "components/AppShell.tsx"), "utf8");
  const merchantBranch = source.slice(source.indexOf('if (pathname.startsWith("/merchant"))'), source.indexOf("return (", source.indexOf('if (pathname.startsWith("/merchant"))') + 1));

  assert.match(source, /function ProductFooter/);
  assert.match(source, /599 家台北 active shops/);
  assert.match(source, /Java transaction state/);
  assert.doesNotMatch(merchantBranch, /ProductFooter/);
});
