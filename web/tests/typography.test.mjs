import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import test from "node:test";

const root = join(import.meta.dirname, "..");
const scannedDirs = ["app", "components"];
const disallowedTracking = /\btracking-(?:tight|wide|wider|widest|\[[^\]]+\])/g;

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
