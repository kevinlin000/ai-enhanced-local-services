import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import test from "node:test";

const root = join(import.meta.dirname, "..");
const scannedDirs = ["app", "components"];
const disallowedTracking = /\btracking-(?:tight|wide|wider|widest|\[[^\]]+\])/g;
const disallowedHeavySurface = /\b(?:shadow-2xl|shadow-xl|rounded-\[2rem\]|rounded-3xl)\b/g;

function walk(dir) {
  const entries = readdirSync(dir);
  return entries.flatMap((entry) => {
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) return walk(path);
    return /\.(tsx|ts|css)$/.test(path) ? [path] : [];
  });
}

test("UI typography keeps letter spacing at the default rhythm", () => {
  const offenders = [];

  for (const dir of scannedDirs) {
    for (const file of walk(join(root, dir))) {
      const source = readFileSync(file, "utf8");
      const matches = source.match(disallowedTracking);
      if (!matches) continue;
      offenders.push(`${relative(root, file)}: ${[...new Set(matches)].join(", ")}`);
    }
  }

  assert.deepEqual(offenders, []);
});

test("UI typography caps heavy weights for a lighter product feel", () => {
  const globals = readFileSync(join(root, "app/globals.css"), "utf8");

  assert.match(globals, /\.font-black\s*{\s*font-weight:\s*700;/);
  assert.match(globals, /\.font-extrabold\s*{\s*font-weight:\s*650;/);
  assert.match(globals, /\.font-bold\s*{\s*font-weight:\s*600;/);
  assert.match(globals, /\.font-semibold\s*{\s*font-weight:\s*550;/);
});

test("primary AI and home surfaces avoid heavy demo-style cards", () => {
  const offenders = [];
  const files = ["app/page.tsx", "app/ai/page.tsx"];

  for (const file of files) {
    const source = readFileSync(join(root, file), "utf8");
    const matches = source.match(disallowedHeavySurface);
    if (!matches) continue;
    offenders.push(`${file}: ${[...new Set(matches)].join(", ")}`);
  }

  assert.deepEqual(offenders, []);
});
